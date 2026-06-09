import re
import time
import json
import logging
from string import Template

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from django.conf import settings
from django.db import connection

from apps.query.models import QueryHistory
from apps.datasets.models import DataRow

logger = logging.getLogger(__name__)

# ===== Prompt 模板化管理 =====

SQL_GENERATE_SYSTEM = Template("""你是一个专业的SQL生成助手。根据以下信息生成PostgreSQL SQL查询。

数据存储在 dataset_rows 表中，每行数据存储在 data 字段(JSONB)中。

具体列名:
$column_info

样本数据(前3行):
$sample_rows

字段值枚举:
$field_values

相似查询案例:
$few_shot_cases

规则:
1. 只生成 SELECT 语句
2. 使用 data->>'列名' 获取文本值，data->'列名' 获取JSON值
3. 如需数值比较，使用 (data->>'列名')::numeric
4. 不要使用 LIMIT 以外的结果限制方式
5. 必须包含 WHERE dataset_id = '$dataset_id' 条件
""")

SQL_GENERATE_USER = Template("用户问题: $question\n\n请生成SQL查询（只输出SQL语句，不要解释）:")

SQL_FIX_SYSTEM = Template("""你是一个SQL修复专家。之前生成的SQL执行失败了，请根据错误信息修复SQL。

具体列名:
$column_info

样本数据:
$sample_rows

字段值枚举:
$field_values
""")

SQL_FIX_USER = Template("问题: $question\n\n失败的SQL: $failed_sql\n\n错误信息: $error_msg\n\n请生成修复后的SQL（只输出SQL语句）:")


class NL2SQLService:
    """自然语言转SQL服务

    7步工作流：Schema发现→SQL生成→安全验证→执行→失败重试→结果格式化

    三个增强设计:
    1. Prompt 模板化 — string.Template，方便迭代调优
    2. Few-shot 案例库 — 从 QueryHistory 注入成功查询案例
    3. 字段值枚举注入 — DISTINCT top 20，减少 LLM 幻觉
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
        return {
            'column_info': self._get_column_info(),
            'sample_rows': self._get_sample_rows(),
            'field_values': self._get_field_values(),
            'few_shot_cases': self._get_few_shot_cases(),
        }

    def _get_column_info(self) -> str:
        row = DataRow.objects.filter(dataset=self.dataset).first()
        if not row or not isinstance(row.data, dict):
            return '无列信息'

        lines = []
        for col, val in row.data.items():
            if isinstance(val, bool):
                vtype = 'boolean'
            elif isinstance(val, int):
                vtype = 'integer'
            elif isinstance(val, float):
                vtype = 'numeric'
            else:
                vtype = 'text'
            lines.append(f"  - {col} ({vtype})")
        return '\n'.join(lines)

    def _get_sample_rows(self) -> str:
        rows = DataRow.objects.filter(dataset=self.dataset)[:3]
        data = [row.data for row in rows]
        return json.dumps(data, ensure_ascii=False, default=str) if data else '无样本数据'

    def _get_field_values(self) -> str:
        rows = DataRow.objects.filter(dataset=self.dataset)[:200]
        if not rows:
            return ''

        columns = []
        for row in rows:
            if isinstance(row.data, dict):
                for col in row.data:
                    if col not in columns:
                        columns.append(col)

        lines = []
        for col in columns[:10]:
            distinct = set()
            for row in rows:
                if isinstance(row.data, dict) and col in row.data:
                    val = row.data[col]
                    if val is not None:
                        distinct.add(str(val))
                    if len(distinct) >= 20:
                        break
            if distinct:
                lines.append(f"  {col}: {', '.join(list(distinct)[:20])}")
        return '\n'.join(lines) if lines else ''

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

    def _generate_sql(self, question: str, schema_info: dict) -> str:
        prompt = ChatPromptTemplate.from_messages([
            ('system', SQL_GENERATE_SYSTEM.safe_substitute(
                column_info=schema_info['column_info'],
                sample_rows=schema_info['sample_rows'],
                field_values=schema_info['field_values'],
                few_shot_cases=schema_info['few_shot_cases'],
                dataset_id=str(self.dataset.id),
            )),
            ('human', SQL_GENERATE_USER.safe_substitute(question=question)),
        ])
        chain = prompt | self.llm
        response = chain.invoke({})
        return self._clean_sql(response.content)

    def _regenerate_sql(self, question: str, failed_sql: str,
                        error_msg: str, schema_info: dict) -> str:
        prompt = ChatPromptTemplate.from_messages([
            ('system', SQL_FIX_SYSTEM.safe_substitute(
                column_info=schema_info['column_info'],
                sample_rows=schema_info['sample_rows'],
                field_values=schema_info['field_values'],
            )),
            ('human', SQL_FIX_USER.safe_substitute(
                question=question,
                failed_sql=failed_sql,
                error_msg=error_msg,
            )),
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
        return [dict(zip(columns, row)) for row in rows]

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
