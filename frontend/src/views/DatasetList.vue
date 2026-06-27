<template>
  <div class="page-container">
    <div class="page-header">
      <h2>数据集管理</h2>
      <el-button
        v-if="canUpload"
        type="primary"
        :icon="Upload"
        @click="showUploadDialog = true"
      >
        上传数据集
      </el-button>
    </div>

    <div class="page-section">
      <el-table :data="datasets" v-loading="loading" stripe>
        <el-table-column prop="name" label="名称" min-width="150" />
        <el-table-column prop="file_name" label="文件名" min-width="150" />
        <el-table-column label="行数" width="90">
          <template #default="{ row }">{{ row.row_count || '-' }}</template>
        </el-table-column>
        <el-table-column label="列数" width="90">
          <template #default="{ row }">{{ row.column_count || '-' }}</template>
        </el-table-column>
        <el-table-column label="状态" width="130">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">
              {{ statusLabel(row.status) }}
            </el-tag>
            <div v-if="row.status === 'processing' && row._progressRows" class="progress-text">
              {{ row._progressRows.toLocaleString() }} 行
            </div>
          </template>
        </el-table-column>
        <el-table-column label="大小" width="100">
          <template #default="{ row }">{{ formatSize(row.file_size) }}</template>
        </el-table-column>
        <el-table-column label="创建时间" width="170">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="goDetail(row.id)">查看</el-button>
            <el-button
              v-if="canUpload"
              link type="danger"
              @click="handleDelete(row)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <div class="pagination-row">
      <el-pagination
        v-model:current-page="page"
        :page-size="20"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="onPageChange"
      />
    </div>

    <el-dialog v-model="showUploadDialog" title="上传数据集" width="540px" :close-on-click-modal="false">
      <el-form label-width="80px">
        <el-form-item label="文件" required>
          <el-upload
            ref="uploadRef"
            v-model:file-list="fileList"
            :auto-upload="false"
            multiple
            :limit="10"
            accept=".csv,.xlsx,.xls"
            :on-change="onFileChange"
            :on-exceed="onExceed"
          >
            <el-button type="primary">选择文件</el-button>
            <template #tip>
              <div class="el-upload__tip">
                支持 .csv / .xlsx / .xls，单个文件最大 50MB，不超过 10 万行 / 100 列；可批量选择，最多 10 个
              </div>
            </template>
          </el-upload>
        </el-form-item>
        <el-form-item v-if="fileList.length === 1" label="名称">
          <el-input v-model="uploadName" placeholder="留空则使用文件名" />
        </el-form-item>
        <el-form-item v-else-if="fileList.length > 1" label=" ">
          <span class="batch-hint">已选 {{ fileList.length }} 个文件，将分别以各自文件名上传</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showUploadDialog = false">取消</el-button>
        <el-button type="primary" :loading="uploading" @click="handleUpload">
          上传{{ fileList.length > 1 ? `（${fileList.length} 个）` : '' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { Upload } from '@element-plus/icons-vue'
import { useUserStore } from '../stores/user'
import { datasetApi, createProgressSocket } from '../api/dataset'
import { ElMessage, ElMessageBox } from 'element-plus'

const router = useRouter()
const store = useUserStore()
const loading = ref(false)
const datasets = ref<any[]>([])
const total = ref(0)
const page = ref(1)

const canUpload = computed(() => {
  const role = store.user?.role
  return role === 'admin' || role === 'analyst'
})

const showUploadDialog = ref(false)
const uploading = ref(false)
const uploadName = ref('')
const fileList = ref<any[]>([])
const uploadRef = ref()
// 活跃的 WebSocket 连接：datasetId → WebSocket（组件卸载时统一关闭）
const sockets = new Map<string, WebSocket>()

onMounted(() => fetchList())

onUnmounted(() => {
  sockets.forEach(s => s.readyState === WebSocket.OPEN && s.close())
  sockets.clear()
})

async function fetchList() {
  loading.value = true
  try {
    const res = await datasetApi.getList(page.value)
    datasets.value = res.data.results
    total.value = res.data.count
  } finally {
    loading.value = false
  }
}

function onPageChange(p: number) {
  page.value = p
  fetchList()
}

function onFileChange(file: any) {
  // 前置文件大小校验（与服务端 MAX_FILE_SIZE = 50MB 对齐）
  // 本地秒拒，避免上传一半才被服务端 413 拒绝
  const MAX_FILE_SIZE = 50 * 1024 * 1024
  if (file.size > MAX_FILE_SIZE) {
    ElMessage.error(`${file.name} 超过 50MB 上限，已忽略`)
    // 过滤掉超限文件（v-model:file-list 受控，直接改数组即可）
    fileList.value = fileList.value.filter((f: any) => f.uid !== file.uid)
  }
}

function onExceed() {
  ElMessage.warning('一次最多上传 10 个文件')
}

async function handleUpload() {
  if (fileList.value.length === 0) {
    ElMessage.warning('请选择文件')
    return
  }
  // 拷贝当前列表，避免上传过程中 fileList 被清空影响循环
  const files = [...fileList.value]
  uploading.value = true

  let successCount = 0
  let asyncCount = 0
  const failures: string[] = []

  try {
    // 逐个上传：复用现有单文件接口 /api/datasets/，后端零改动。
    // 不并发（用 for await 串行）：避免浏览器同域 6 连接限制 + 后端
    // 大文件 Celery worker（concurrency=2）被打满。一个失败不影响其余。
    for (const f of files) {
      const fd = new FormData()
      fd.append('file', f.raw)
      // 只在单文件时支持自定义名称（多文件时各自用文件名）
      if (files.length === 1 && uploadName.value) {
        fd.append('name', uploadName.value)
      }
      try {
        const res = await datasetApi.upload(fd)
        successCount++
        if (res.data.status === 'completed') {
          // 同步处理完成，无需订阅进度
        } else {
          asyncCount++
          subscribeProgress(res.data.id)
        }
      } catch (e: any) {
        // 单个失败不中断：413/409/500 等，收集错误信息最后汇总
        const msg = e?.response?.data?.error || '上传失败'
        failures.push(`${f.name}: ${msg}`)
      }
    }

    // 汇总提示
    if (successCount === 1 && failures.length === 0) {
      // 单文件成功：保持原有提示语义
      if (asyncCount === 0) ElMessage.success('上传并处理成功')
      else ElMessage.success('上传成功，正在处理中...')
    } else if (successCount > 0 && failures.length === 0) {
      // 批量全部成功
      ElMessage.success(`成功上传 ${successCount} 个文件${asyncCount ? '，正在处理中...' : ''}`)
    } else if (successCount > 0 && failures.length > 0) {
      // 批量部分成功
      ElMessage.warning(
        `${successCount} 个成功，${failures.length} 个失败：` + failures.join('；')
      )
    } else {
      // 全失败
      ElMessage.error('全部失败：' + failures.join('；'))
    }

    // 关闭弹窗 + 清理（只有全部失败时不关弹窗，让用户改了重试）
    if (successCount > 0) {
      showUploadDialog.value = false
      fileList.value = []
      uploadName.value = ''
      uploadRef.value?.clearFiles()
      fetchList()
    }
  } finally {
    uploading.value = false
  }
}

/**
 * 订阅数据集处理进度（WebSocket）
 * 收到 processing 时实时更新行状态，收到 completed/failed 时关闭连接
 */
function subscribeProgress(id: string) {
  const socket = createProgressSocket(
    id,
    (data) => {
      const row = datasets.value.find((d: any) => d.id === id)
      if (!row) return

      if (data.status === 'processing') {
        row.status = 'processing'
        row._progressRows = data.progress
      } else if (data.status === 'completed') {
        row.status = 'completed'
        ElMessage.success(`数据集 "${row.name}" 处理完成`)
        socket.close()
        sockets.delete(id)
        fetchList()
      } else if (data.status === 'failed') {
        row.status = 'failed'
        ElMessage.error('数据集处理失败')
        socket.close()
        sockets.delete(id)
      }
    },
    () => {
      // WebSocket 异常（后端不可用等）：回退一次性 HTTP 查询兜底
      sockets.delete(id)
      datasetApi.getDetail(id).then((res) => {
        if (res.data.status === 'completed' || res.data.status === 'failed') {
          fetchList()
        }
      }).catch(() => { /* interceptor 处理 */ })
    },
  )
  sockets.set(id, socket)
}

async function handleDelete(row: any) {
  await ElMessageBox.confirm(`确定删除数据集 "${row.name}"？`, '确认删除', { type: 'warning' })
  try {
    await datasetApi.delete(row.id)
    ElMessage.success('删除成功')
    fetchList()
  } catch { /* interceptor handles error message */ }
}

function goDetail(id: string) {
  router.push({ name: 'dataset-detail', params: { id } })
}

function statusType(s: string) {
  const map: Record<string, string> = { completed: 'success', processing: '', pending: 'info', failed: 'danger' }
  return map[s] || 'info'
}

function statusLabel(s: string) {
  const map: Record<string, string> = { completed: '已完成', processing: '处理中', pending: '等待中', failed: '失败' }
  return map[s] || s
}

function formatSize(bytes: number) {
  if (!bytes) return '-'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

function formatTime(t: string) {
  if (!t) return '-'
  return t.replace('T', ' ').slice(0, 19)
}
</script>

<style scoped>
.progress-text {
  margin-top: 2px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  line-height: 1.2;
}
.batch-hint {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
</style>
