<template>
  <div class="page-container">
    <div class="stat-cards">
      <div
        class="stat-card stagger-item"
        v-for="(card, i) in statCards"
        :key="i"
        :style="{ '--stagger-index': i, '--card-accent': card.color }"
      >
        <el-icon class="decorative-icon"><component :is="card.icon" /></el-icon>
        <div class="stat-number">{{ card.value }}</div>
        <div class="stat-label">{{ card.label }}</div>
      </div>
    </div>

    <div class="page-section">
      <div class="section-header">
        <h3>最近数据集</h3>
        <el-button link type="primary" @click="$router.push('/datasets')">查看全部</el-button>
      </div>
      <el-table :data="recentDatasets" stripe size="small">
        <el-table-column prop="name" label="名称" min-width="150" />
        <el-table-column label="行数" width="80">
          <template #default="{ row }">{{ row.row_count || '-' }}</template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.status === 'completed' ? 'success' : 'info'" size="small">
              {{ row.status === 'completed' ? '已完成' : '处理中' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="时间" width="160">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="60">
          <template #default="{ row }">
            <el-button link type="primary" @click="goDetail(row.id)">查看</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { DataAnalysis, FolderOpened, User } from '@element-plus/icons-vue'
import { useUserStore } from '../stores/user'
import { datasetApi } from '../api/dataset'
import { queryApi } from '../api/query'

const router = useRouter()
const store = useUserStore()
const datasetCount = ref(0)
const queryCount = ref(0)
const recentDatasets = ref<any[]>([])

const statCards = computed(() => [
  { label: '数据集总数', value: datasetCount.value, icon: FolderOpened, color: '#3a8fd4' },
  { label: '查询记录数', value: queryCount.value, icon: DataAnalysis, color: '#2ecc71' },
  {
    label: '当前角色',
    value: store.user?.role === 'admin' ? '管理员' : store.user?.role === 'analyst' ? '分析师' : '只读用户',
    icon: User,
    color: '#e6a23c',
  },
])

onMounted(async () => {
  try {
    const [dsRes, qRes] = await Promise.all([
      datasetApi.getList(),
      queryApi.getHistory(),
    ])
    datasetCount.value = dsRes.data.count
    queryCount.value = qRes.data.count
    recentDatasets.value = dsRes.data.results.slice(0, 5)
  } catch { /* interceptor handles error */ }
})

function goDetail(id: string) {
  router.push({ name: 'dataset-detail', params: { id } })
}

function formatTime(t: string) {
  if (!t) return '-'
  return t.replace('T', ' ').slice(0, 19)
}
</script>

<style scoped>
.stat-cards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-lg);
  margin-bottom: var(--space-lg);
}

.stat-card {
  position: relative;
  padding: var(--space-lg);
  background: var(--brand-surface);
  border-radius: 12px;
  box-shadow: var(--brand-shadow-sm);
  overflow: hidden;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--brand-shadow-md);
}

.stat-card::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 4px;
  background: var(--card-accent, var(--brand-accent));
  border-radius: 0 2px 2px 0;
}

.decorative-icon {
  position: absolute;
  right: 16px;
  top: 50%;
  transform: translateY(-50%);
  font-size: 48px;
  opacity: 0.08;
  color: var(--card-accent, var(--brand-accent));
}

.stat-number {
  font-size: 36px;
  font-weight: 700;
  color: var(--card-accent, var(--brand-accent));
  margin-bottom: 4px;
  line-height: 1.2;
}

.stat-label {
  font-size: 13px;
  color: var(--brand-text-tertiary);
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-md);
}

.section-header h3 {
  font-size: 16px;
  font-weight: 600;
  color: var(--brand-text-primary);
}
</style>
