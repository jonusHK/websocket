<script>
import { reactive, computed, onMounted } from 'vue';

export default {
  name: 'App',
  props: {
    title: String
  },
  setup (props, { emit }) {
    const state = reactive({
      username: '',
      password: '',
      lowerCaseUsername: computed(() => state.username.toLowerCase()),
    })
    const login = () => {
      emit('login', {
        username: state.username,
        password: state.password
      })
    }
    const onResizeChatBodyList = ({ width, height}) => {
    }
    onMounted(() => {
      console.log('title: ' + props.title)
    })
    return { 
      login,
      onResizeChatBodyList,
      state
    }
  },
  components: {
  }
}
</script>

<template>
  <div id="chat-container">
    <div id="chat-menu">
      <div class="chat-menu-icon">
        <div>
          <ui-icon>person</ui-icon>
          <ui-icon>chat_bubble</ui-icon>
        </div>
        <div>
          <!-- <ui-icon>notifications</ui-icon> -->
          <!-- <ui-icon>notifications_off</ui-icon> -->
          <ui-icon>settings</ui-icon>
        </div>
      </div>
    </div>
    <div id="chat-header">
      <div class="chat-header-icon">
        <ui-icon style="margin-right:10px;">search</ui-icon>
        <ui-icon>person_add_alt_1</ui-icon>
        <!-- <ui-icon>add_comment</ui-icon> -->
      </div>
    </div>
    <div id="chat-body">
      <div class="chat-body-container">
        <div class="chat-body-list" v-resize="onResizeChatBodyList">
          <div>
            <p v-for="i in 36" :key="i">Chat Body List {{ i }}</p>
          </div>
        </div> <!-- 채팅방 목록 or 친구 목록 -->
        <div class="chat-body-detail">
          <div class="chat-body-detail-summary">
            <div>
              방 상세 정보
            </div>
          </div>
          <div class="chat-body-detail-view">
            <p v-for="i in 36" :key="i">Chat Body Detail View {{ i }}</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
#app {
  font-family: Avenir, Helvetica, Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  text-align: center;
  color: #2c3e50;
  margin-top: 10px;
  width: 100vw;
  height: 100vh;
}

#chat-container {
  width: 100%;
  height: 100%;
  overflow: auto;
  position: relative;
}

#chat-menu {
  position: fixed;
  top: 0;
  left: 0;
  width: 100px;
  height: 100%;
  background-color: #eeeeee;
  z-index: 1;
}

.chat-menu-icon {
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  align-items: center;
}

.chat-menu-icon div:nth-child(1) {
  height: 100%;
  margin-top: 100px;
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  align-items: center;
}

.chat-menu-icon div:nth-child(2) {
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  align-items: center;
}

.chat-menu-icon div .material-icons {
  margin-bottom: 40px;
}

#chat-header {
  position: fixed;
  top: 0;
  left: 100px;
  right: 0;
  height: 70px;
  padding-left: 30px;
  padding-right: 30px;
  z-index: 1;
  background-color: #fdd835;
}

.chat-header-icon {
  height: 100%;
  display: flex; 
  flex-direction: row; 
  justify-content: flex-end; 
  align-items: center;
  z-index: 50;
}

#chat-body {
  position: fixed;
  left: 100px;
  top: 70px;
  width: 100%;
  height: calc(100% - 70px);
}

.chat-body-container {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: row;
}

.chat-body-list {
  width: 300px;
  height: 100%;
  resize: horizontal;
  overflow: auto;
}

.chat-body-list div {
  width: 100%;
  height: 100%;
  padding-left: 15px;
}

.chat-body-detail {
  width: calc(100% - 400px);
}

.chat-body-detail-summary {
  position: sticky;
  background-color: #ffffff;
  top: 0;
  left: 0;
  height: 50px;
  padding-left: 15px;
  border-bottom: 1px solid #e0e0e0;
}

.chat-body-detail-summary div {
  display: flex;
  flex-direction: row;
  align-items: center;
  height: 100%;
}

.chat-body-detail-view {
  height: calc(100% - 50px);
  padding-left: 15px;
  overflow: auto;
}

</style>
