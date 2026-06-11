import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import './styles/variables.css'
import 'element-plus/dist/index.css'
import './styles/element-overrides.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'

import App from './App.vue'
import router from './router'
import './styles/index.css'
import './styles/transitions.css'

const app = createApp(App)

for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

app.use(createPinia())
app.use(router)
app.use(ElementPlus, { locale: { el: { pagination: { goto: '前往', pagesize: '条/页', total: '共 {total} 条', pageClassifier: '页' } } } })
app.mount('#app')
