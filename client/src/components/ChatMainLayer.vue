<script>
import { reactive, computed, onMounted, getCurrentInstance } from 'vue';
import FollowingListLayer from './FollowingListLayer.vue';
import FollowingInfoLayer from './FollowingInfoLayer.vue';

export default {
  name: 'ChatMainLayer',
  setup (props, { emit }) {
    const { proxy } = getCurrentInstance();
    const state = reactive({
      chatBodyListView: {
        following: true,
        chat: false,
      },
      chatBodyInfoView: {
        following: false,
        chat: false,
      },
      userProfileId: null,
      chatRoomId: null,
    })
    if (proxy.$store.state.user.userId === '' || proxy.$store.state.user.userIsActive === false) {
      proxy.$router.replace('/login');
    }
    const onResizeChatBodyList = ({ width, height}) => {
      // TODO
    }
    const onChangeChatMenuType = (type) => {
      for (const key in state.chatBodyListView) {
        if (key === type) {
          state.chatBodyListView[key] = true;
        } else {
          state.chatBodyListView[key] = false;
        }
      }
      for (const key in state.chatBodyInfoView) {
        state.chatBodyInfoView[key] = false;
      }
    }
    const followingDetail = function(userProfileId) {
      for (const key in state.chatBodyListView) {
        if (key === 'following') {
          state.chatBodyListView[key] = true;
        } else {
          state.chatBodyListView[key] = false;
        }
      }
      for (const key in state.chatBodyInfoView) {
        if (key === 'following') {
          state.chatBodyInfoView[key] = true;
        } else {
          state.chatBodyInfoView[key] = false;
        }
      }
      state.userProfileId = userProfileId;
    }
    const closeFollowingInfo = function() {
      state.chatBodyInfoView['following'] = false;
    }
    return {
      state,
      onResizeChatBodyList,
      onChangeChatMenuType,
      followingDetail,
      closeFollowingInfo,
    }
  },
  components: {
    FollowingListLayer,
    FollowingInfoLayer,
}
}
</script>

<template>
  <div id="chat-container">
    <div id="chat-menu">
      <div class="chat-menu-icon">
        <div>
          <ui-icon
            @click="onChangeChatMenuType('following')"
            :style="{
              cursor: 'pointer',
              color: state.chatBodyListView['following'] ? '#000000' : '#bdbdbd',
            }"
          >
            person
          </ui-icon>
          <p style="margin: 0;">
            <ui-badge overlap :count="8" style="margin: 0;">
              <ui-icon
                @click="onChangeChatMenuType('chat')"
                :style="{
                  cursor: 'pointer',
                  color: state.chatBodyListView['chat'] ? '#000000' : '#bdbdbd',
                }"
              >
                chat_bubble
              </ui-icon>
            </ui-badge>
          </p>
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
      </div>
    </div>
    <div id="chat-body">
      <div class="chat-body-container">
        <div class="chat-body-list" v-resize="onResizeChatBodyList">
          <FollowingListLayer 
            v-if="state.chatBodyListView['following']"
            @followingDetail="followingDetail"
          />
          <div v-if="state.chatBodyListView['chat']">
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
        <div 
          class="chat-body-info" 
          v-if="state.chatBodyInfoView['following']"
        >
          <FollowingInfoLayer
            v-if="state.chatBodyInfoView['following']"
            :userProfileId="state.userProfileId"
            @closeFollowingInfo="closeFollowingInfo"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
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
  background-color: #6200ee;
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
  width: calc(100% - 100px);
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
  min-width: 150px;
  height: 100%;
  resize: horizontal;
  overflow: auto;
}

.chat-body-list div {
  width: 100%;
  height: 100%;
}

.chat-body-detail {
  width: calc(100% - 300px);
  resize: horizontal;
  overflow: auto;
}

.chat-body-info {
  width: 400px;
  min-width: 300px;
  right: 0;
  height: 100%;
}
</style>
