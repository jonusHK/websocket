<script>
import { reactive, computed, onMounted, getCurrentInstance } from 'vue';
import FollowingListLayer from './FollowingListLayer.vue';
import FollowingInfoLayer from './FollowingInfoLayer.vue';
import ChatListLayer from './ChatListLayer.vue';
import ChatDetailLayer from './ChatDetailLayer.vue';
import ChatInfoLayer from './ChatInfoLayer.vue';
import _ from 'lodash';

export default {
  name: 'ChatMainLayer',
  setup (props, { emit }) {
    const { proxy } = getCurrentInstance();
    const followingListSocket = new WebSocket(`ws://localhost:8000/api/v1/chats/followings/${proxy.$store.getters['user/getProfileId']}`);
    const chatRoomListSocket = new WebSocket(`ws://localhost:8000/api/v1/chats/rooms/${proxy.$store.getters['user/getProfileId']}`);
    const state = reactive({
      chatBodyListView: {
        following: true,
        chat: false,
      },
      chatBodyDetailView: {
        following: false,
        chat: false,
      },
      chatBodyInfoView: {
        following: false,
        chat: false,
      },
      userProfileId: null,
      chatRoomId: null,
      followings: [],
      chatRooms: [],
      totalUnreadMsgCnt: 0,
    })
    if (proxy.$store.state.user.userId === '' || proxy.$store.state.user.userIsActive === false) {
      proxy.$router.replace('/login');
    }
    const onChangeChatMenuType = (type) => {
      for (const key in state.chatBodyListView) {
        if (key === type) {
          state.chatBodyListView[key] = true;
        } else {
          state.chatBodyListView[key] = false;
        }
      }
      for (const key in state.chatBodyDetailView) {
        state.chatBodyDetailView[key] = false;
      }
      for (const key in state.chatBodyInfoView) {
        state.chatBodyInfoView[key] = false;
      }
    }
    const followingInfo = function(userProfileId) {
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
    const getTotalUnreadMsgCnt = function(cnt) {
      state.totalUnreadMsgCnt = cnt;
    }
    const chatDetail = function(chatRoomId) {
      for (const key in state.chatBodyListView) {
        if (key === 'chat') {
          state.chatBodyListView[key] = true;
        } else {
          state.chatBodyListView[key] = false;
        }
      }
      for (const key in state.chatBodyDetailView) {
        if (key === 'chat') {
          state.chatBodyDetailView[key] = true;
        } else {
          state.chatBodyDetailView[key] = false;
        }
      }
      for (const key in state.chatBodyInfoView) {
        state.chatBodyInfoView[key] = false;
      }
      state.chatRoomId = chatRoomId;
    }
    const chatInfo = function(chatRoomId) {
      for (const key in state.chatBodyInfoView) {
        if (key === 'chat') {
          state.chatBodyInfoView[key] = true;
        } else {
          state.chatBodyInfoView[key] = false;
        }
      }
      state.chatRoomId = chatRoomId;
    }
    const closeChatInfo = function() {
      state.chatBodyInfoView['chat'] = false;
    }
    onMounted(() => {
      followingListSocket.onopen = function(event) {
          console.log('친구 목록 웹소켓 연결 성공');
      }
      followingListSocket.onmessage = function(event) {
          const followings = _.orderBy(JSON.parse(event.data), ['nickname'], ['asc']);
          state.followings = _.filter(followings, function(f) {
              return f.is_hidden === false && f.is_forbidden === false;
          });    
      }
      followingListSocket.onclose = function(event) {
          console.log('close - ', event);
          proxy.$router.replace('/login');
      }
      followingListSocket.onerror = function(event) {
          console.log('error - ', event);
          proxy.$router.replace('/login');
      }
      chatRoomListSocket.onopen = function(event) {
          console.log('채팅방 목록 웹소켓 연결 성공');
      }
      chatRoomListSocket.onmessage = function(event) {
          state.chatRooms = _.orderBy(JSON.parse(event.data), ['timestamp'], 'desc');
          let totalUnreadMsgCnt = 0;
          for (const room of state.chatRooms) {
              totalUnreadMsgCnt += room.unread_msg_cnt;
          }
          state.totalUnreadMsgCnt = totalUnreadMsgCnt;
      }
      chatRoomListSocket.onclose = function(event) {
          console.log('close - ', event);
          proxy.$router.replace('/login');
      }
      chatRoomListSocket.onerror = function(event) {
          console.log('error - ', event);
          proxy.$router.replace('/login');
      }
    });
    return {
      state,
      onChangeChatMenuType,
      followingInfo,
      closeFollowingInfo,
      getTotalUnreadMsgCnt,
      chatDetail,
      chatInfo,
      closeChatInfo,
    }
  },
  components: {
    FollowingListLayer,
    FollowingInfoLayer,
    ChatListLayer,
    ChatDetailLayer,
    ChatInfoLayer,
  },
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
            <ui-badge overlap :count="state.totalUnreadMsgCnt" style="margin: 0;">
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
        <FollowingListLayer 
          v-if="state.chatBodyListView['following']"
          :followings="state.followings"
          @followingInfo="followingInfo"
        />
        <FollowingInfoLayer
          v-if="state.chatBodyInfoView['following']"
          :userProfileId="state.userProfileId"
          @closeFollowingInfo="closeFollowingInfo"
        />
        <ChatListLayer
          v-if="state.chatBodyListView['chat']"
          :chatRooms="state.chatRooms"
          @chatDetail="chatDetail"
          @chatInfo="chatInfo"
        />
        <ChatDetailLayer
          v-if="state.chatBodyDetailView['chat']"
          :chatRoomId="state.chatRoomId"
          @followingInfo="followingInfo"
        />
        <ChatInfoLayer
          v-if="state.chatBodyInfoView['chat']"
          :chatRoomId="state.chatRoomId"
          @closeChatInfo="closeChatInfo"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
</style>
