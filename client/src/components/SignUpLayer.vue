<script>
import { reactive, getCurrentInstance } from 'vue';
import { useValidator, helpers } from 'balm-ui';

const { VITE_SERVER_HOST } = import.meta.env;
const validations = [
    {
        key: 'email',
        label: '이메일 주소',
        validator: 'email',
    },
    {
        key: 'password',
        label: '비밀번호',
        validator: 'password',
    },
    {
        key: 'passwordAgain',
        label: '비밀번호 확인',
        validator: 'repasswordRule',
        repasswordRule: {
            validate(value, data) {
                return value === data.password;
            },
            message: '동일한 비밀번호가 입력되지 않았습니다.'
        },
    },
    {
        key: 'name',
        label: '이름',
        validator: 'name',
    },
    {
        key: 'mobile',
        label: '휴대폰 번호',
        validator: 'mobile',
    },
]

export default {
    setup() {
        const { proxy } = getCurrentInstance();
        proxy.$store.dispatch('user/logout');
        const validator = useValidator();
        const state = reactive({
            formData: {
                email: '',
                password: '',
                passwordAgain: '',
                name: '',
                mobile: '',
            },
            message: '',
        });
        const signUp = () => {
            const { valid, message } = validator.validate(state.formData);
            state.message = message;
            if (!valid) {
                return;
            }
            try {
                proxy.$axios.post(VITE_SERVER_HOST + '/v1/users/signup', JSON.stringify({
                    name: state.formData.name,
                    mobile: state.formData.mobile,
                    email: state.formData.email,
                    password: state.formData.password,
                }), {
                    headers: {
                        "Content-Type": `application/json`,
                    },
                })
                .then((res) => {
                    if (res.status === 201) {
                        proxy.$alert({
                            message: '회원가입이 성공적으로 완료되었습니다.',
                            state: 'success',
                            stateOutlined: true
                        })
                        proxy.$router.push({ path: '/login', name: 'Login', query: {}});
                    }
                })
                .catch((err) => {
                    const error_obj = {
                        state: 'error',
                        stateOutlined: true                        
                    }
                    if (err.response.data.code === 'ALREADY_SIGNED_UP') {
                        error_obj['message'] = '이미 동일한 이메일 주소로 가입되어 있습니다.';
                    } else if (err.response.data.code === 'INVALID_UID') {
                        error_obj['message'] = '이메일 주소가 올바르지 않습니다.';
                    } else if (err.response.data.code === 'INVALID_PASSWORD') {
                        error_obj['message'] = '비밀번호가 올바르지 않습니다.'
                    } else if (err.response.data.code === 'INVALID_USER_NAME') {
                        error_obj['message'] = '이름이 올바르지 않습니다.';
                    } else if (err.response.data.code === 'INVALID_MOBILE') {
                        error_obj['message'] = '휴대폰 번호가 올바르지 않습니다.';
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
        const cancel = () => {
            proxy.$router.go(-1);
        }
        return {
            state,
            signUp,
            cancel,
            validations,
        }
    }
}
</script>

<template>
    <div class="menu-background-layout">
        <div class="menu-signup-layout">
            <p class="text menu-title">회원가입</p>
            <div class="menu-form-layout">
                <ui-textfield required v-model="state.formData.email" class="menu-textfield">이메일 주소</ui-textfield>
                <ui-textfield 
                    input-type="password" 
                    required 
                    v-model="state.formData.password" 
                    class="menu-textfield"
                >
                    비밀번호
                </ui-textfield>
                <ui-textfield 
                    input-type="password" 
                    required 
                    v-model="state.formData.passwordAgain" 
                    class="menu-textfield"
                >
                    비밀번호 확인
                </ui-textfield>
                <ui-textfield required v-model="state.formData.name" class="menu-textfield">이름</ui-textfield>
                <ui-textfield required v-model="state.formData.mobile" class="menu-textfield">휴대폰 번호</ui-textfield>
                <div>
                    <ui-button raised @click="signUp" style="margin-right: 5px;">가입</ui-button>
                    <ui-button outlined @click="cancel">취소</ui-button>
                </div>
            </div>
            <div>
                <ui-alert v-if="state.message" state="error">{{ state.message }}</ui-alert>
            </div>
        </div>
    </div>
</template>