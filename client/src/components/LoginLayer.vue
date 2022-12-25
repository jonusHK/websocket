<script>
import { reactive, getCurrentInstance } from 'vue';

const { VITE_SERVER_HOST } = import.meta.env;

export default {
    setup () {
        const { proxy } = getCurrentInstance();
        proxy.$store.dispatch('user/logout');
        const state = reactive({
            email: '',
            password: ''
        });
        const login = () => {
            try {
                proxy.$axios.post(VITE_SERVER_HOST + "/users/login", JSON.stringify({
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
                            userId: res.data.data.user.id,
                            userEmail: res.data.data.user.email,
                            userMobile: res.data.data.user.mobile,
                            userName: res.data.data.user.name,
                            userIsActive: res.data.data.user.is_active,
                            profileId: res.data.data.profile.id,
                            profileNickname: res.data.data.profile.nickname,
                            profileStatusMessage: res.data.data.profile.status_message,
                            profileImages: res.data.data.profile.images,
                            profileIsDefault: res.data.data.profile.is_default,
                            profileIsActive: res.data.data.profile.is_active,
                        });
                        proxy.$router.push({ path: '/', name: 'Home', query: {} });
                    }
                })
                .catch((err) => {
                    const error_obj = {
                        state: 'error',
                        stateOutlined: true                        
                    }
                    if (err.response.data.code === 'INVALID_UID') {
                        error_obj['message'] = '이메일 주소가 올바르지 않습니다.';
                    } else if (err.response.data.code === 'INVALID_PASSWORD') {
                        error_obj['message'] = '비밀번호가 올바르지 않습니다.'
                    } else {
                        error_obj['message'] = err.response.data.message;
                    }
                    proxy.$alert(error_obj);
                })
            } catch (error) {
                proxy.$alert({
                    message: `에러 발생 (${error})`,
                    state: 'error',
                    stateOutlined: true
                });
            }
        }
        const signUp = () => {
            proxy.$router.push({ path: '/signup', name: 'SignUp', query: {}});
        }
        return {
            state,
            login,
            signUp,
        }
    },
}
</script>

<template>
    <div class="menu-background-layout">
        <div class="menu-login-layout">
            <p class="text menu-title">로그인</p>
            <div class="menu-form-layout">
                <ui-textfield v-model="state.email" class="menu-textfield">이메일 주소</ui-textfield>
                <ui-textfield input-type="password" v-model="state.password" class="menu-textfield">비밀번호</ui-textfield>
                <div>
                    <ui-button raised @click="login" style="margin-right: 5px;">로그인</ui-button>
                </div>
                <div style="margin-top: 10px;">
                    <p class="signUpBtn" @click="signUp">회원가입</p>
                </div>
            </div>
        </div>
    </div>
</template>

<style>
.signUpBtn {
    font-size: 13px;
    color: #6200ee;
    text-decoration: underline;
    cursor: pointer;
}
</style>