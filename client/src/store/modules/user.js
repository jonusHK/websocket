const user = {
    namespaced: true,
    state: {
        userId: '',
        userEmail: '',
        userMobil: '',
        userName: '',
        userIsActive: false,
    },
    getters: {
        getUserId(state) {
            return state.userId;
        },
        getUserEmail(state) {
            return state.userEmail;
        },
        getUserName(state) {
            return state.userName;
        },
        getUserIsActive(state) {
            return state.userIsActive;
        }
    },
    actions: {
        login({ commit }, value) {
            commit('loginUser', value);
        },
        logout({ commit }) {
            commit('logoutUser');
        }
    },
    mutations: {
        loginUser(state, value) {
            state.userId = value.userId
            state.userEmail = value.userEmail
            state.userMobile = value.userMobile
            state.userName = value.userName
            state.userIsActive = value.userIsActive
        },
        logoutUser(state) {
            state.userId = ''
            state.userEmail = ''
            state.userMobil = ''
            state.userName = ''
            state.userIsActive = false
        }
    }
}

export default user;