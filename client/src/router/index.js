import { createWebHistory, createRouter } from "vue-router";

const routes = [
  {
    path: "/",
    name: 'Home',
    component: () => import('@/components/MainLayer.vue'),
  },
  {
    path: "/login",
    name: "Login",
    component: () => import('@/components/LoginLayer.vue'),
  },
  {
    path: "/chat",
    name: "Chat",
    component: () => import('@/components/ChatMainLayer.vue'),
  }
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

export default router;