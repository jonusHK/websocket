<script>
import { reactive, onMounted } from 'vue';
import ChatMainLayer from '@/components/ChatMainLayer.vue';
import LoginLayer from '@/components/LoginLayer.vue';

export default {
    name: 'Main',
    setup () {
        const state = reactive({
            loggedIn: false,
        })
        onMounted(() => {
            console.log('loggedIn - ', state.loggedIn);
        })
        return {
            state
        }
    },
    components: {
        ChatMainLayer,
        LoginLayer
    }
}
</script>

<template>
    <ChatMainLayer v-if="state.loggedIn" />
    <LoginLayer v-else />
</template>