<template>
  <el-container class="main-layout">
    <el-aside :width="isCollapse ? '64px' : '200px'" class="sidebar">
      <div class="logo">
        <span class="logo-icon">◈</span>
        <span v-show="!isCollapse" class="logo-text">AI 数据分析</span>
      </div>
      <el-menu
        :default-active="activeMenu"
        :collapse="isCollapse"
        router
      >
        <el-menu-item index="/">
          <el-icon><DataAnalysis /></el-icon>
          <template #title>仪表盘</template>
        </el-menu-item>
        <el-menu-item index="/datasets">
          <el-icon><FolderOpened /></el-icon>
          <template #title>数据集</template>
        </el-menu-item>
        <el-menu-item index="/query/history">
          <el-icon><Clock /></el-icon>
          <template #title>查询历史</template>
        </el-menu-item>
        <el-menu-item v-if="isAdmin" index="/users/manage">
          <el-icon><User /></el-icon>
          <template #title>用户管理</template>
        </el-menu-item>
      </el-menu>
      <div class="sidebar-gradient"></div>
    </el-aside>

    <el-container>
      <el-header class="top-bar">
        <el-icon class="collapse-btn" @click="isCollapse = !isCollapse">
          <Fold v-if="!isCollapse" />
          <Expand v-else />
        </el-icon>
        <div class="user-area">
          <el-dropdown>
            <span class="user-name">
              <span class="user-avatar">{{ avatarLetter }}</span>
              {{ store.user?.username }}
              <el-tag size="small" :type="roleTagType" class="role-tag">{{ roleLabel }}</el-tag>
              <el-icon><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="handleLogout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <el-main>
        <router-view v-slot="{ Component, route: childRoute }">
          <transition name="route" mode="out-in">
            <component :is="Component" :key="childRoute.path" />
          </transition>
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '../stores/user'
import { userApi } from '../api/user'
import { ElMessage } from 'element-plus'

const route = useRoute()
const router = useRouter()
const store = useUserStore()
const isCollapse = ref(false)

store.initFromStorage()

const activeMenu = computed(() => {
  if (route.path.startsWith('/datasets')) return '/datasets'
  return route.path
})

const isAdmin = computed(() => store.user?.role === 'admin')

const avatarLetter = computed(() => (store.user?.username || 'U')[0].toUpperCase())

const roleLabel = computed(() => {
  const map: Record<string, string> = { admin: '管理员', analyst: '分析师', viewer: '只读用户' }
  return map[store.user?.role || 'viewer']
})

const roleTagType = computed(() => {
  const map: Record<string, string> = { admin: 'danger', analyst: 'warning', viewer: 'info' }
  return map[store.user?.role || 'viewer'] as any
})

async function handleLogout() {
  try {
    await userApi.logout()
  } finally {
    store.clearUser()
    ElMessage.success('已退出登录')
    router.push({ name: 'login' })
  }
}
</script>

<style scoped>
.main-layout {
  height: 100vh;
}

.sidebar {
  background-color: var(--brand-sidebar-bg);
  transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  position: relative;
}

.logo {
  height: var(--topbar-height);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: var(--brand-sidebar-text-active);
  font-size: 18px;
  font-weight: 600;
  border-bottom: 1px solid var(--brand-sidebar-border);
  flex-shrink: 0;
}

.logo-icon {
  font-size: 22px;
  color: var(--brand-accent);
}

.logo-text {
  white-space: nowrap;
}

.sidebar-gradient {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 80px;
  background: linear-gradient(to top, rgba(0, 0, 0, 0.15), transparent);
  pointer-events: none;
}

.el-menu {
  border-right: none;
  background-color: var(--brand-sidebar-bg) !important;
  --el-menu-bg-color: var(--brand-sidebar-bg);
  --el-menu-text-color: var(--brand-sidebar-text);
  --el-menu-active-color: var(--brand-sidebar-text-active);
  --el-menu-hover-bg-color: var(--brand-sidebar-hover);
  flex: 1;
}

:deep(.el-menu-item) {
  color: var(--brand-sidebar-text);
  border-left: 3px solid transparent;
  transition: all 0.2s ease;
  white-space: nowrap;
}

:deep(.el-menu-item:hover) {
  background-color: var(--brand-sidebar-hover) !important;
  color: var(--brand-sidebar-text-active);
}

:deep(.el-menu-item.is-active) {
  background-color: var(--brand-sidebar-active) !important;
  color: var(--brand-sidebar-text-active) !important;
  border-left-color: var(--brand-accent);
}

.top-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--brand-surface);
  box-shadow: var(--brand-shadow-sm);
  z-index: 1;
}

.collapse-btn {
  font-size: 20px;
  cursor: pointer;
  color: var(--brand-text-secondary);
  transition: color 0.2s;
}

.collapse-btn:hover {
  color: var(--brand-text-primary);
}

.user-area {
  display: flex;
  align-items: center;
}

.user-name {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  color: var(--brand-text-secondary);
  font-size: 14px;
  transition: color 0.2s;
}

.user-name:hover {
  color: var(--brand-text-primary);
}

.user-avatar {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--brand-accent), var(--el-color-primary-dark-2));
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 600;
}

.role-tag {
  margin-left: 4px;
}
</style>
