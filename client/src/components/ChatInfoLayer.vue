<script>
import { reactive, watch, onMounted, getCurrentInstance, toRef, nextTick } from 'vue';
import constants from '../constants';

const { VITE_SERVER_HOST } = import.meta.env;


export default {
    name: 'ChatInfoLayer',
    props: {
        chatRoom: Object,
    },
    setup (props, { emit }) {
        const { proxy } = getCurrentInstance();
        const state = reactive({
            room: toRef(props, 'chatRoom'),
        });
    }
}
</script>

<template>
    <div></div>
</template>