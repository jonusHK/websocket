<script>
import { reactive, watch, onMounted, getCurrentInstance, toRef, nextTick } from 'vue';
import constants from '../constants';

const { VITE_SERVER_HOST } = import.meta.env;


export default {
    name: 'ChatInfoLayer',
    props: {
        chatRoomId: Number,
    },
    setup (props, { emit }) {
        const { proxy } = getCurrentInstance();
        const state = reactive({
            roomId: toRef(props, 'chatRoomId'),
        });
    }
}
</script>

<template>
    <div></div>
</template>