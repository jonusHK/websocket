const user = {
    namespaced: true,
    state: {
        userId: '',
        userEmail: '',
        userMobile: '',
        userName: '',
        userIsActive: false,
        profileId: '',
        profileNickname: '',
        profileStatusMessage: '',
        profileImages: [],
        profileIsDefault: false,
        profileIsActive: false,
    },
    getters: {
        getUserId(state) {
            return state.userId;
        },
        getUserEmail(state) {
            return state.userEmail;
        },
        getUserMobile(state) {
            return state.userMobile;
        },
        getUserName(state) {
            return state.userName;
        },
        getUserIsActive(state) {
            return state.userIsActive;
        },
        getProfileId(state) {
            return state.profileId;
        },
        getProfileNickname(state) {
            return state.profileNickname;
        },
        getProfileStatusMessage(state) {
            return state.profileStatusMessage;
        },
        getProfileImages(state) {
            return state.profileImages;
        },
        getProfileIsDefault(state) {
            return state.profileIsDefault;
        },
        getProfileIsActive(state) {
            return state.profileIsActive;
        },
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
            state.userId = value.userId;
            state.userEmail = value.userEmail;
            state.userMobile = value.userMobile;
            state.userName = value.userName;
            state.userIsActive = value.userIsActive;
            state.profileId = value.profileId;
            state.profileNickname = value.profileNickname;
            state.profileStatusMessage = value.profileStatusMessage;
            state.profileImages = value.profileImages;
            state.profileIsDefault = value.profileIsDefault;
            state.profileIsActive = value.profileIsActive;
        },
        logoutUser(state) {
            state.userId = '';
            state.userEmail = '';
            state.userMobile = '';
            state.userName = '';
            state.userIsActive = false;
            state.profileId = '';
            state.profileNickname = '';
            state.profileStatusMessage = '';
            state.profileImages = [];
            state.profileIsDefault = false;
            state.profileIsActive = false;
        }
    }
}

export default user;