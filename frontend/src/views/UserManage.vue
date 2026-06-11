<template>
  <div class="page-container">
    <div class="page-header">
      <h2>用户管理</h2>
    </div>

    <div class="page-section">
      <el-table :data="users" v-loading="loading" stripe>
        <el-table-column prop="username" label="用户名" min-width="120" />
        <el-table-column prop="email" label="邮箱" min-width="180">
          <template #default="{ row }">
            <span class="text-secondary">{{ row.email || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="角色" width="160">
          <template #default="{ row }">
            <el-select
              v-model="row.role"
              size="small"
              @change="handleRoleChange(row)"
              :disabled="row.id === currentUserId"
            >
              <el-option label="管理员" value="admin" />
              <el-option label="分析师" value="analyst" />
              <el-option label="只读用户" value="viewer" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'danger'" size="small">
              {{ row.is_active ? '正常' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="注册时间" width="170">
          <template #default="{ row }">{{ formatTime(row.date_joined) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="80">
          <template #default="{ row }">
            <el-button
              v-if="row.id !== currentUserId && row.is_active"
              link type="danger"
              @click="handleDisable(row)"
            >
              禁用
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useUserStore } from '../stores/user'
import { userApi } from '../api/user'
import { ElMessage, ElMessageBox } from 'element-plus'

const store = useUserStore()
const loading = ref(false)
const users = ref<any[]>([])
const currentUserId = computed(() => store.user?.id)

onMounted(() => fetchUsers())

async function fetchUsers() {
  loading.value = true
  try {
    const res = await userApi.getUserList()
    users.value = res.data
  } finally {
    loading.value = false
  }
}

async function handleRoleChange(row: any) {
  try {
    await userApi.updateUserRole(row.id, row.role)
    ElMessage.success('角色已更新')
  } catch {
    fetchUsers()
  }
}

async function handleDisable(row: any) {
  await ElMessageBox.confirm(`确定禁用用户 "${row.username}"？`, '确认', { type: 'warning' })
  try {
    await userApi.disableUser(row.id)
    ElMessage.success('用户已禁用')
    fetchUsers()
  } catch { /* interceptor handles error message */ }
}

function formatTime(t: string) {
  if (!t) return '-'
  return t.replace('T', ' ').slice(0, 19)
}
</script>
