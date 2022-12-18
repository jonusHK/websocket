import { createApp } from 'vue'
import App from './App.vue'
import store from './store';
import router from './router';
import BalmUI from 'balm-ui'; // Official Google Material Components
import BalmUIPlus from 'balm-ui-plus'; // BalmJS Team Material Components
import 'balm-ui-css';
import VueResizeObserver from 'vue-resize-observer';
import jQuery from 'jquery';

const app = createApp(App);

app.use(store);
app.use(router);
app.use(BalmUI);
app.use(BalmUIPlus);
app.use(VueResizeObserver);

global.$ = jQuery

app.mount('#app');
