import { createWebHistory, createRouter } from 'vue-router';


const routes = [
  {
    path: '/',
    name: 'Home',
    component: () => import('@/components/MainLayer.vue'),
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/components/LoginLayer.vue'),
  },
  {
    path: '/signup',
    name: 'SignUp',
    component: () => import('@/components/SignUpLayer.vue'),
  }
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

export default router;