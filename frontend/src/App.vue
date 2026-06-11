<template>
  <router-view v-slot="{ Component, route }">
    <transition name="route" mode="out-in">
      <component :is="Component" :key="route.path" />
    </transition>
  </router-view>
</template>
