<template>
  <div class="page-container">
    <div class="page-header">
      <h2>查询历史</h2>
      <el-select v-model="filterDatasetId" placeholder="按数据集筛选" clearable @change="fetchHistory">
        <el-option
          v-for="ds in datasetOptions"
          :key="ds.id"
          :label="ds.name"
          :value="ds.id"
        />
      </el-select>
    </div>

    <div class="page-section">
      <el-table :data="records" v-loading="loading" stripe>
        <el-table-column prop="dataset_name" label="数据集" min-width="120" />
        <el-table-column prop="question" label="问题" min-width="200" show-overflow-tooltip />
        <el-table-column label="SQL" min-width="250">
          <template #default="{ row }">
            <el-tooltip :content="row.generated_sql" placement="top">
              <span class="sql-preview">{{ row.generated_sql }}</span>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.is_success ? 'success' : 'danger'" size="small">
              {{ row.is_success ? '成功' : '失败' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="耗时" width="90">
          <template #default="{ row }">{{ row.execution_time_ms ? row.execution_time_ms + 'ms' : '-' }}</template>
        </el-table-column>
        <el-table-column label="时间" width="170">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="80">
          <template #default="{ row }">
            <el-button link type="primary" @click="goDetail(row.dataset)">查看</el-button>
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
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { queryApi } from '../api/query'
import { datasetApi } from '../api/dataset'

const router = useRouter()
const loading = ref(false)
const records = ref<any[]>([])
const total = ref(0)
const page = ref(1)
const filterDatasetId = ref('')
const datasetOptions = ref<any[]>([])

onMounted(async () => {
  fetchHistory()
  const res = await datasetApi.getList()
  datasetOptions.value = res.data.results
})

async function fetchHistory() {
  loading.value = true
  try {
    const params: any = { page: page.value }
    if (filterDatasetId.value) params.dataset_id = filterDatasetId.value
    const res = await queryApi.getHistory(params)
    records.value = res.data.results
    total.value = res.data.count
  } finally {
    loading.value = false
  }
}

function onPageChange(p: number) {
  page.value = p
  fetchHistory()
}

function goDetail(datasetId: string) {
  router.push({ name: 'dataset-detail', params: { id: datasetId } })
}

function formatTime(t: string) {
  if (!t) return '-'
  return t.replace('T', ' ').slice(0, 19)
}
</script>

<style scoped>
.sql-preview {
  display: inline-block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: var(--brand-font-mono);
  font-size: 12px;
  color: var(--brand-text-secondary);
  background: var(--brand-code-bg);
  padding: 2px 8px;
  border-radius: 4px;
}
</style>
