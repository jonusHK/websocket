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
import validatorRules from './config/validator-rules';
import './assets/main.css';
import dayjs from 'dayjs';
import 'dayjs/locale/ko';
import $confirm from 'balm-ui/plugins/confirm';

const app = createApp(App);

axios.defaults.withCredentials = true;
app.config.globalProperties.$axios = axios;
app.config.globalProperties.$router = router;
app.config.globalProperties.$store = store;
dayjs.locale('ko');
app.config.globalProperties.$dayjs = dayjs;

app.use(store);
app.use(router);
app.use(BalmUI, {
    $validator: validatorRules,
    $confirm: {},
    UiTooltip: {},
    UiCheckbox: {},
});
app.use(BalmUIPlus);
app.use(VueResizeObserver);

window.$ = jQuery;

app.mount('#app');
