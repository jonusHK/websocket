<script>
import { reactive, getCurrentInstance, toRef } from 'vue';

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