<script>
import { reactive, computed, onMounted, getCurrentInstance } from 'vue';
import FollowingListLayer from './FollowingListLayer.vue';
import FollowingInfoLayer from './FollowingInfoLayer.vue';
import ChatListLayer from './ChatListLayer.vue';
import ChatDetailLayer from './ChatDetailLayer.vue';

export default {
  name: 'ChatMainLayer',
  setup (props, { emit }) {
    const { proxy } = getCurrentInstance();
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
      for (const key in state.chatBodyInfoView) {
        state.chatBodyInfoView[key] = false;
      }
    }
    const followingDetail = function(userProfileId) {
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
      state.chatRoomId = chatRoomId;
    }
    return {
      state,
      onChangeChatMenuType,
      followingDetail,
      closeFollowingInfo,
    }
  },
  components: {
    FollowingListLayer,
    FollowingInfoLayer,
    ChatListLayer,
    ChatDetailLayer,
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
        <FollowingListLayer 
          v-if="state.chatBodyListView['following']"
          @followingDetail="followingDetail"
        />
        <FollowingInfoLayer
          v-if="state.chatBodyInfoView['following']"
          :userProfileId="state.userProfileId"
          @closeFollowingInfo="closeFollowingInfo"
        />
        <ChatListLayer
          v-if="state.chatBodyListView['chat']"
          @chatDetail="chatDetail"
        />
        <ChatDetailLayer
          v-if="state.chatBodyDetailView['chat']"
          :chatRoomId="state.chatRoomId"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
</style>
