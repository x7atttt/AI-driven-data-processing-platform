<template>
  <AuthLayout>
    <template #title>注册账号</template>
    <template #subtitle>创建账户以使用数据分析平台</template>
    <el-form :model="form" @submit.prevent="handleRegister">
      <el-form-item>
        <el-input v-model="form.username" placeholder="用户名" :prefix-icon="User" size="large" />
      </el-form-item>
      <el-form-item>
        <el-input v-model="form.email" placeholder="邮箱" :prefix-icon="Message" size="large" />
      </el-form-item>
      <el-form-item>
        <el-input v-model="form.password" type="password" placeholder="密码" :prefix-icon="Lock" size="large" show-password />
      </el-form-item>
      <el-form-item>
        <el-input v-model="form.confirmPassword" type="password" placeholder="确认密码" :prefix-icon="Lock" size="large" show-password />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" size="large" :loading="loading" native-type="submit">注册</el-button>
      </el-form-item>
    </el-form>
    <div class="link-row">
      已有账号？<router-link to="/login">去登录</router-link>
    </div>
  </AuthLayout>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { User, Lock, Message } from '@element-plus/icons-vue'
import { userApi } from '../api/user'
import { ElMessage } from 'element-plus'
import AuthLayout from '../components/AuthLayout.vue'

const router = useRouter()
const loading = ref(false)
const form = ref({ username: '', email: '', password: '', confirmPassword: '' })

async function handleRegister() {
  if (!form.value.username || !form.value.password || !form.value.email) {
    ElMessage.warning('请填写完整信息')
    return
  }
  if (form.value.password !== form.value.confirmPassword) {
    ElMessage.warning('两次密码不一致')
    return
  }
  loading.value = true
  try {
    await userApi.register({
      username: form.value.username,
      password: form.value.password,
      email: form.value.email,
    })
    ElMessage.success('注册成功，请登录')
    router.push({ name: 'login' })
  } finally {
    loading.value = false
  }
}
</script>
