import { createWebHistory, createRouter } from "vue-router";
import LoginLayer from "@/components/LoginLayer.vue";
import ChatDefaultLayer from "@/components/ChatDefaultLayer.vue";

const routes = [
  {
    path: "/login",
    name: "Login",
    component: LoginLayer,
  },
  {
    path: "/chat",
    name: "Chat",
    component: ChatDefaultLayer,
  }
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

export default router;