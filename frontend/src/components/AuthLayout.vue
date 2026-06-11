<template>
  <div class="auth-page">
    <div class="auth-bg-shapes">
      <div class="shape shape-1"></div>
      <div class="shape shape-2"></div>
      <div class="shape shape-3"></div>
    </div>
    <div class="auth-card">
      <div class="auth-brand">
        <div class="auth-logo">◈</div>
        <h2><slot name="title">AI 数据分析平台</slot></h2>
        <p v-if="$slots.subtitle" class="auth-subtitle"><slot name="subtitle"></slot></p>
      </div>
      <slot></slot>
    </div>
  </div>
</template>

<style scoped>
.auth-page {
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #1b2838;
  position: relative;
  overflow: hidden;
  padding-right: 10%;
}

.auth-bg-shapes .shape {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  pointer-events: none;
}

.shape-1 {
  width: 400px;
  height: 400px;
  background: var(--brand-sidebar-bg);
  opacity: 0.4;
  top: -100px;
  left: -100px;
}

.shape-2 {
  width: 300px;
  height: 300px;
  background: var(--brand-accent);
  opacity: 0.15;
  bottom: -50px;
  right: 10%;
}

.shape-3 {
  width: 200px;
  height: 200px;
  background: var(--brand-accent-secondary);
  opacity: 0.1;
  top: 40%;
  right: 30%;
}

.auth-card {
  position: relative;
  width: 420px;
  padding: 40px;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border-radius: 16px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  box-shadow: var(--brand-shadow-lg);
  z-index: 1;
}

.auth-brand {
  text-align: center;
  margin-bottom: 28px;
}

.auth-logo {
  font-size: 36px;
  color: var(--brand-accent);
  margin-bottom: 8px;
}

.auth-brand h2 {
  font-size: 22px;
  font-weight: 700;
  color: var(--brand-text-primary);
  margin-bottom: 4px;
}

.auth-subtitle {
  font-size: 14px;
  color: var(--brand-text-tertiary);
}

.auth-card :deep(.el-form-item) {
  margin-bottom: 20px;
}

.auth-card :deep(.el-button--primary) {
  width: 100%;
  height: 44px;
  font-weight: 600;
  border-radius: 8px;
  background: linear-gradient(135deg, var(--brand-accent), var(--el-color-primary-dark-2));
  border: none;
  transition: transform 0.2s, box-shadow 0.2s;
}

.auth-card :deep(.el-button--primary:hover) {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(58, 143, 212, 0.4);
}

.link-row {
  text-align: center;
  font-size: 14px;
  color: var(--brand-text-tertiary);
  margin-top: 4px;
}
</style>
