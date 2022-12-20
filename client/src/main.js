import { createApp } from 'vue'
import App from './App.vue'
import store from './store';
import router from './router';
import BalmUI from 'balm-ui'; // Official Google Material Components
import BalmUIPlus from 'balm-ui-plus'; // BalmJS Team Material Components
import 'balm-ui-css';
import VueResizeObserver from 'vue-resize-observer';
import jQuery from 'jquery';
import axios from 'axios'
import './assets/main.css';

const app = createApp(App);

axios.defaults.withCredentials = true;
app.config.globalProperties.$axios = axios;
app.config.globalProperties.$router = router;
app.config.globalProperties.$store = store;

app.use(store);
app.use(router);
app.use(BalmUI);
app.use(BalmUIPlus);
app.use(VueResizeObserver);

global.$ = jQuery

app.mount('#app');
