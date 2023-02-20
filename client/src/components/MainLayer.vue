<script>
import { reactive, onMounted, getCurrentInstance } from 'vue';
import ChatMainLayer from './ChatMainLayer.vue';
import { useCookies } from 'vue3-cookies';

const { cookies } = useCookies();

export default {
    name: 'Main',
    setup () {
        const { proxy } = getCurrentInstance();
        const state = reactive({
            loggedIn: false
        })
        onMounted(() => {
            if (proxy.$store.state.user.userId !== '' && proxy.$store.state.user.userIsActive === true) {
                state.loggedIn = true;
            } else {
                proxy.$router.replace('/login');
            }
        })
        return {
            state
        }
    },
    components: {
        ChatMainLayer
    }
}
</script>

<template>
    <ChatMainLayer v-if="state.loggedIn" />
</template>