<script>
import { reactive, onMounted, getCurrentInstance } from 'vue';
import axios from 'axios';
import router from '@/router';

const { VITE_SERVER_HOST } = import.meta.env;

export default {
    setup () {
        const { proxy } = getCurrentInstance();
        proxy.$store.dispatch('user/logout');
        const state = reactive({
            email: '',
            password: ''
        })
        const login = () => {
            try {
                axios.post(VITE_SERVER_HOST + "/users/login", JSON.stringify({
                    uid: state.email,
                    password: state.password,
                }), {
                headers: {
                    "Content-Type": `application/json`,
                },
                })
                .then((res) => {
                    if (res.status === 200) {
                        proxy.$store.dispatch('user/login', {
                            userId: res.data.data.id,
                            userEmail: res.data.data.email,
                            userMobile: res.data.data.mobile,
                            userName: res.data.data.name,
                            userIsActive: res.data.data.is_active
                        });
                        router.push({ path: '/', name: 'Home', query: {} });
                    }
                }).catch((error) => {
                    if (error.response.data.code === 'INVALID_UID') {
                        proxy.$alert({
                            message: '이메일 주소가 올바르지 않습니다.',
                            state: 'error',
                            stateOutlined: true
                        });
                    } else if (error.response.data.code === 'INVALID_PASSWORD') {
                        proxy.$alert({
                            message: '비밀번호가 올바르지 않습니다.',
                            state: 'error',
                            stateOutlined: true
                        })
                    }
                })
            } catch (error) {
                proxy.$alert({
                    message: `에러 발생 (${error})`,
                    state: 'error',
                    stateOutlined: true
                })
            }
        }
        return {
            state,
            login
        }
    },
}
</script>

<template>
    <div style="display: flex; flex-direction: row; justify-content: center; align-items: center; width: 100%; height: 100%; background-color: #6200ee;">
        <div style="display: flex; flex-direction: row; justify-content: center; align-items: center; width: 600px; height: 400px; background-color: white; border-radius: 10px;">
            <div style="width: 300px; height: 500px; display: flex; flex-direction: column; align-items: center; justify-content: center;">
                <ui-textfield v-model="state.email" style="width: 100%; margin-bottom: 20px;">이메일 주소</ui-textfield>
                <ui-textfield input-type="password" v-model="state.password" style="width: 100%; margin-bottom: 20px;">비밀번호</ui-textfield>
                <div>
                    <ui-button raised @click="login" style="margin-right: 5px;">로그인</ui-button>
                    <ui-button outlined>취소</ui-button>
                </div>
            </div>
        </div>
    </div>
</template>
