import re
import time
import logging
import json
from decimal import Decimal
from datetime import datetime, date
from string import Template

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from django.conf import settings
from django.db import connection

from apps.query.models import QueryHistory

logger = logging.getLogger(__name__)


def _sanitize_for_json(obj):
    """递归把数据库返回的非 JSON 原生类型转成可序列化的类型。

    PostgreSQL cursor 返回的行里常含 Decimal（numeric 列）、
    datetime/date（时间列）、UUID 等，这些标准 json.dumps 不认识，
    直接塞进 JSONField 会抛 TypeError。统一在这里净化，让结果既能
    存 result_preview，也能直接走 DRF Response。
    """
    if isinstance(obj, Decimal):
        # Decimal → float（数值语义保留，舍弃精确精度，前端展示足够）
        return float(obj)
    if isinstance(obj, (datetime, date)):
        # datetime/date → ISO 格式字符串（前端可解析）
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize_for_json(v) for v in obj]
    return obj


# ===== Prompt 模板化管理 =====

SQL_GENERATE_SYSTEM = Template("""你是一个专业的SQL生成助手。根据以下信息生成PostgreSQL SQL查询。

数据存储在 dataset_rows 表中，每行数据存储在 data 字段(JSONB)中。

$schema_summary

相似查询案例:
$few_shot_cases

规则:
1. 只生成 SELECT 语句
2. 使用 data->>'列名' 获取文本值，data->'列名' 获取JSON值
3. 如需数值比较，使用 (data->>'列名')::numeric
4. 不要使用 LIMIT 以外的结果限制方式
5. 必须包含 WHERE dataset_id = '$dataset_id' 条件
6. 使用 ORDER BY 排序时必须加 NULLS LAST（PostgreSQL 默认 DESC 时 NULL 排最前，会让空值占满 LIMIT 结果）
""")

SQL_GENERATE_USER = Template("用户问题: $question\n\n请生成SQL查询（只输出SQL语句，不要解释）:")

SQL_FIX_SYSTEM = Template("""你是一个SQL修复专家。之前生成的SQL执行失败了，请根据错误信息修复SQL。

$schema_summary

规则:
1. ORDER BY 排序时必须加 NULLS LAST（PostgreSQL 默认 DESC 时 NULL 排最前）
""")

SQL_FIX_USER = Template("问题: $question\n\n失败的SQL: $failed_sql\n\n错误信息: $error_msg\n\n请生成修复后的SQL（只输出SQL语句）:")


class NL2SQLService:
    """自然语言转SQL服务

    7步工作流：Schema发现→SQL生成→安全验证→执行→失败重试→结果格式化

    三个增强设计:
    1. Prompt 模板化 — string.Template，方便迭代调优
    2. Few-shot 案例库 — 从 QueryHistory 注入成功查询案例
    3. Analyzer 驱动的 Schema 发现 — 统计摘要 + 样本 + 字段值，替代简陋的手动探测
    """

    MAX_RETRIES = 3

    DANGEROUS_KEYWORDS = [
        'DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER',
        'CREATE', 'TRUNCATE', 'EXEC', 'EXECUTE',
        'GRANT', 'REVOKE',
    ]

    def __init__(self, dataset):
        self.dataset = dataset
        self.llm = ChatOpenAI(
            model=settings.LLM_MODEL,
            temperature=0,
            openai_api_key=settings.OPENAI_API_KEY,
            openai_api_base=settings.OPENAI_API_BASE,
        )

    # ===== Schema 发现 =====

    def _discover_schema(self) -> dict:
        from apps.datasets.services.analyzer import get_schema_summary
        return {
            'schema_summary': get_schema_summary(self.dataset),
            'few_shot_cases': self._get_few_shot_cases(),
        }

    def _get_few_shot_cases(self) -> str:
        cases = QueryHistory.objects.filter(
            dataset=self.dataset, is_success=True
        ).order_by('-created_at')[:3]
        if not cases:
            return '无'
        return '\n\n'.join(
            f"问题: {c.question}\nSQL: {c.generated_sql}" for c in cases
        )

    # ===== SQL 安全 =====

    def _validate_sql(self, sql: str) -> bool:
        sql_stripped = sql.strip().upper()
        if not sql_stripped.startswith('SELECT'):
            return False
        for keyword in self.DANGEROUS_KEYWORDS:
            if re.search(rf'\b{keyword}\b', sql_stripped):
                return False
        if ';' in sql_stripped[:-1]:
            return False
        return True

    def _add_limit(self, sql: str) -> str:
        if 'LIMIT' not in sql.upper():
            sql = sql.rstrip(';') + ' LIMIT 1000'
        return sql

    def _clean_sql(self, sql: str) -> str:
        sql = sql.strip()
        if sql.startswith('```'):
            sql = sql.split('\n', 1)[1] if '\n' in sql else sql[3:]
        if sql.endswith('```'):
            sql = sql.rsplit('```', 1)[0]
        return sql.strip()

    # ===== SQL 生成 =====

    @staticmethod
    def _escape_braces(text: str) -> str:
        """转义花括号，避免 ChatPromptTemplate 误解析 JSON"""
        return text.replace('{', '{{').replace('}', '}}')

    def _generate_sql(self, question: str, schema_info: dict) -> str:
        prompt = ChatPromptTemplate.from_messages([
            ('system', self._escape_braces(SQL_GENERATE_SYSTEM.safe_substitute(
                schema_summary=schema_info['schema_summary'],
                few_shot_cases=schema_info['few_shot_cases'],
                dataset_id=str(self.dataset.id),
            ))),
            ('human', self._escape_braces(SQL_GENERATE_USER.safe_substitute(
                question=question,
            ))),
        ])
        chain = prompt | self.llm
        response = chain.invoke({})
        return self._clean_sql(response.content)

    def _regenerate_sql(self, question: str, failed_sql: str,
                        error_msg: str, schema_info: dict) -> str:
        prompt = ChatPromptTemplate.from_messages([
            ('system', self._escape_braces(SQL_FIX_SYSTEM.safe_substitute(
                schema_summary=schema_info['schema_summary'],
            ))),
            ('human', self._escape_braces(SQL_FIX_USER.safe_substitute(
                question=question,
                failed_sql=failed_sql,
                error_msg=error_msg,
            ))),
        ])
        chain = prompt | self.llm
        response = chain.invoke({})
        return self._clean_sql(response.content)

    # ===== SQL 执行 =====

    def _execute_sql(self, sql: str) -> list:
        with connection.cursor() as cursor:
            cursor.execute(sql)
            columns = [col[0] for col in cursor.description]
            rows = cursor.fetchall()
        # 净化 Decimal/datetime 等非 JSON 类型，保证存 JSONField 和 HTTP Response 都安全
        return [_sanitize_for_json(dict(zip(columns, row))) for row in rows]

    # ===== 主流程 =====

    def query(self, question: str) -> dict:
        start_time = time.time()

        # 1. Schema发现
        schema_info = self._discover_schema()

        # 2. SQL生成
        sql = self._generate_sql(question, schema_info)

        # 3. 安全审查
        if not self._validate_sql(sql):
            elapsed = int((time.time() - start_time) * 1000)
            return {
                'error': '生成的SQL包含不允许的操作，仅支持SELECT查询',
                'sql': sql,
                'success': False,
                'retry_count': 0,
                'execution_time_ms': elapsed,
            }

        # 4. 自动加LIMIT
        sql = self._add_limit(sql)

        # 5. SQL执行 + 自动重试
        retry_count = 0
        for attempt in range(self.MAX_RETRIES + 1):
            try:
                results = self._execute_sql(sql)
                elapsed = int((time.time() - start_time) * 1000)
                return {
                    'sql': sql,
                    'success': True,
                    'retry_count': retry_count,
                    'execution_time_ms': elapsed,
                    'data': results,
                    'row_count': len(results),
                }
            except Exception as e:
                retry_count += 1
                logger.warning(
                    "SQL执行失败 (尝试 %d/%d): %s",
                    retry_count, self.MAX_RETRIES, e,
                )
                if attempt < self.MAX_RETRIES:
                    sql = self._regenerate_sql(
                        question, sql, str(e), schema_info
                    )
                    if not self._validate_sql(sql):
                        elapsed = int((time.time() - start_time) * 1000)
                        return {
                            'error': '修复后的SQL仍包含不允许的操作',
                            'sql': sql,
                            'success': False,
                            'retry_count': retry_count,
                            'execution_time_ms': elapsed,
                        }
                    sql = self._add_limit(sql)
                else:
                    elapsed = int((time.time() - start_time) * 1000)
                    return {
                        'sql': sql,
                        'error': str(e),
                        'success': False,
                        'retry_count': retry_count,
                        'execution_time_ms': elapsed,
                    }
