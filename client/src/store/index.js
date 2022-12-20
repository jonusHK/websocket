import { createStore } from 'vuex';
import user from './modules/user';
import createPersistedState from 'vuex-persistedstate';

const storageState = createPersistedState({
  paths: ['user']
});

export default createStore({
  modules: {
    user,
  },
  plugins: [storageState]
});
