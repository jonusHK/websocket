<script>
import { reactive, watch, onMounted, getCurrentInstance, toRef, nextTick } from 'vue';
import constants from '../constants';

const { VITE_SERVER_HOST } = import.meta.env;


export default {
    name: 'ChatDetailLayer',
    props: {
        chatRoomId: Number,
    },
    setup (props, { emit }) {
        const { proxy } = getCurrentInstance();
        const state = reactive({
            connectedRoomIds: [],
            roomId: toRef(props, 'chatRoomId'),
        });
        const connectRoom = function(roomId) {
            // TODO websocket 연결
        }
        watch(
            () => props.chatRoomId,
            (cur, prev) => {
                // TODO prev display -> show = false;
                if (!state.connectedRoomIds.includes(cur)) {
                    // 웹소켓 연결
                    state.connectedRoomIds.push(cur);
                } else {
                    // 이미 연결된 roomId 인 경우, 특정 display -> show = true;
                }
            }
        )
        onMounted(() => {
            if (!state.connectedRoomIds.includes(state.roomId)) {
                // 웹소켓 연결
                state.connectedRoomIds.push(state.roomId);
            } else {
                // 이미 연결된 roomId 인 경우, 특정 display -> show = true;
            }
        })
    }
}
</script>

<template>
    <div></div>
</template>