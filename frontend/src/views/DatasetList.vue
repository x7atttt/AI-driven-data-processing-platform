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
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">
              {{ statusLabel(row.status) }}
            </el-tag>
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

    <el-dialog v-model="showUploadDialog" title="上传数据集" width="500px" :close-on-click-modal="false">
      <el-form :model="uploadForm" label-width="80px">
        <el-form-item label="文件" required>
          <el-upload
            ref="uploadRef"
            :auto-upload="false"
            :limit="1"
            accept=".csv,.xlsx,.xls"
            :on-change="onFileChange"
            :on-remove="onFileRemove"
          >
            <el-button type="primary">选择文件</el-button>
            <template #tip>
              <div class="el-upload__tip">支持 .csv / .xlsx / .xls</div>
            </template>
          </el-upload>
        </el-form-item>
        <el-form-item label="名称">
          <el-input v-model="uploadForm.name" placeholder="留空则使用文件名" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showUploadDialog = false">取消</el-button>
        <el-button type="primary" :loading="uploading" @click="handleUpload">上传</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { Upload } from '@element-plus/icons-vue'
import { useUserStore } from '../stores/user'
import { datasetApi } from '../api/dataset'
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
const uploadForm = ref({ name: '', file: null as File | null })
const uploadRef = ref()
const pollTimers = ref<ReturnType<typeof setInterval>[]>([])

onMounted(() => fetchList())

onUnmounted(() => {
  pollTimers.value.forEach(clearInterval)
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
  uploadForm.value.file = file.raw
}

function onFileRemove() {
  uploadForm.value.file = null
}

async function handleUpload() {
  if (!uploadForm.value.file) {
    ElMessage.warning('请选择文件')
    return
  }
  uploading.value = true
  try {
    const fd = new FormData()
    fd.append('file', uploadForm.value.file)
    if (uploadForm.value.name) fd.append('name', uploadForm.value.name)
    const res = await datasetApi.upload(fd)

    showUploadDialog.value = false
    uploadForm.value = { name: '', file: null }
    uploadRef.value?.clearFiles()

    if (res.data.status === 'completed') {
      ElMessage.success('上传并处理成功')
    } else {
      ElMessage.success('上传成功，正在处理中...')
      pollStatus(res.data.id)
    }
    fetchList()
  } finally {
    uploading.value = false
  }
}

function pollStatus(id: string) {
  const timer = setInterval(async () => {
    try {
      const res = await datasetApi.getDetail(id)
      if (res.data.status === 'completed') {
        ElMessage.success(`数据集 "${res.data.name}" 处理完成`)
        clearInterval(timer)
        fetchList()
      } else if (res.data.status === 'failed') {
        ElMessage.error('数据集处理失败')
        clearInterval(timer)
      }
    } catch {
      clearInterval(timer)
    }
  }, 3000)
  pollTimers.value.push(timer)
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
