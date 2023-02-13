<script>
import { reactive, onMounted, computed, getCurrentInstance, nextTick, watch } from 'vue';
import FollowingListLayer from './FollowingListLayer.vue';
import FollowingInfoLayer from './FollowingInfoLayer.vue';
import ChatListLayer from './ChatListLayer.vue';
import ChatDetailLayer from './ChatDetailLayer.vue';
import ChatInfoLayer from './ChatInfoLayer.vue';
import _ from 'lodash';
import { looseIndexOf } from '@vue/shared';
const { VITE_SERVER_HOST } = import.meta.env;

export default {
  name: 'ChatMainLayer',
  setup (props, { emit }) {
    const { proxy } = getCurrentInstance();
    const followingListSocket = new WebSocket(`ws://localhost:8000/api/v1/chats/followings/${proxy.$store.getters['user/getProfileId']}`);
    const chatRoomListSocket = new WebSocket(`ws://localhost:8000/api/v1/chats/rooms/${proxy.$store.getters['user/getProfileId']}`);
    const state = reactive({
      loginProfileId: proxy.$store.getters['user/getProfileId'],
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
      chatRoom: null,
      followings: [],
      chatRooms: [],
      totalUnreadMsgCnt: 0,
      showAddUserPopup: false,
      searchProfileIdentityId: '',
      addUserProfile: null,
      searchedProfileIdentityId: '',
      isAlreadyFollowing: false,
      showCreateRoomPopup: false,
      searchFollowingNickname: '',
      selectedFollowingIds: [],
      showSettings: false,
    });
    if (proxy.$store.state.user.userId === '' || proxy.$store.state.user.userIsActive === false) {
      proxy.$router.replace('/login');
    }
    const initData = function() {
      state.userProfileId = null;
      state.chatRoomId = null;
      state.chatRoom = null;
      state.showAddUserPopup = false;
      state.searchProfileIdentityId = '';
      state.searchedProfileIdentityId = '';
      state.isAlreadyFollowing = false;
      state.addUserProfile = null;
      state.showCreateRoomPopup = false;
      state.searchFollowingNickname = '';
      state.selectedFollowingIds = [];
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
      initData();
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
      state.chatRoom = _.filter(state.chatRooms, function(r) {
        return r.id === state.chatRoomId;
      })[0];
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
    const getDefaultProfileImage = function(images) {
      if (images.length > 0) {
          for (const i in images) {
              const image = images[i];
              // type -> 1: 프로필 이미지 2: 배경 이미지
              if (image.type === 1 && image.is_default === true) {
                  return image.url;
              }
          }
          return null;
      }
      return null;
    }
    const onCancelAddUserProfile = function() {
      state.showAddUserPopup = false;
      state.searchProfileIdentityId = '';
      state.addUserProfile = null;
      state.searchedProfileIdentityId = '';
      state.isAlreadyFollowing = false;
    }
    const moveChatRoomDetail = function() {
      proxy.$axios.post(VITE_SERVER_HOST + '/v1/chats/rooms/create', JSON.stringify({
        user_profile_id: state.loginProfileId,
        target_profile_ids: [state.addUserProfile.id]
      }), {
        headers: {
            'Content-Type': 'application/json',
        }
      })
      .then((res) => {
        if (res.status === 201) {
          nextTick(() => {
              setTimeout(() => chatDetail(res.data.data.id), 100);
          });
        } else {
          const error_obj = {
            state: 'error',
            stateOutlined: true,
            message: err.response.data.message
          }
        }
      })
      .catch((err) => {
        const error_obj = {
            state: 'error',
            stateOutlined: true,
            message: err
        }
        proxy.$alert(error_obj);
      })
      .finally(() => {
        onCancelAddUserProfile();
      });
    }
    const onConfirmAddUserProfile = function() {
      if (state.addUserProfile !== null) {
        proxy.$axios.post(VITE_SERVER_HOST + `/v1/users/relationship/${state.loginProfileId}/${state.addUserProfile.id}`)
        .then((res) => {
          if (res.status === 201) {
            proxy.$alert({
              message: '친구가 추가되었습니다.',
              state: 'success',
              stateOutlined: true
            });
            onCancelAddUserProfile();
          } else {
            proxy.$alert({
              message: '친구 추가에 실패했습니다.',
              state: 'error',
              stateOutlined: true
            });
          }
        })
        .catch((err) => {
          proxy.$alert({
            message: '친구 추가에 실패했습니다.',
            state: 'error',
            stateOutlined: true
          });
        })
      } else {
        proxy.$alert({
            message: '추가할 친구를 선택해주세요.',
            state: 'warn',
            stateOutlined: true
        });
      }
    }
    const searchProfile = function(obj) {
      const url = new URL(VITE_SERVER_HOST + '/v1/users/profiles');
      url.search = new URLSearchParams(obj);
      proxy.$axios.get(url)
      .then((res) => {
        if (res.status === 200 && res.data.total >= 1) {
          state.addUserProfile = res.data.data[0];
          state.isAlreadyFollowing = _.filter(state.followings, function(f) {
            return f.id === state.addUserProfile.id;
          }).length >= 1 || state.addUserProfile.id === state.loginProfileId;
        }
      })
      .finally(() => {
        if (_.has(obj, 'identity_id')) {
          state.searchedProfileIdentityId = obj.identity_id;
        }
      })
    }
    const getOneToOneBtnName = function() {
      return state.addUserProfile.id === state.loginProfileId ? '나와의 채팅' : '1:1 대화';
    }
    const searchedFollowings = computed(() => {
      const searchedFollowings = _.filter(state.followings, function(f) {
          return _.includes(f.nickname, state.searchFollowingNickname);
      });
      return searchedFollowings;
    })
    const stopEvent = function(e) {
      e.stopPropagation();
    }
    const onClickProfileId = function(followingId) {
      followingInfo(followingId);
    }
    const onCancelCreateRoom = function() {
      state.showCreateRoomPopup = false;
      state.searchFollowingNickname = '';
      state.selectedFollowingIds = [];
    }
    const onConfirmCreateRoom = function() {
      if (state.selectedFollowingIds.length > 0) {
        proxy.$axios.post(VITE_SERVER_HOST + '/v1/chats/rooms/create', JSON.stringify({
          user_profile_id: state.loginProfileId,
          target_profile_ids: state.selectedFollowingIds
        }), {
          headers: {
              'Content-Type': 'application/json',
          }
        })
        .then((res) => {
          if (res.status === 201) {
            nextTick(() => {
                setTimeout(() => chatDetail(res.data.data.id), 100);
            });
          } else {
            const error_obj = {
              state: 'error',
              stateOutlined: true,
              message: err.response.data.message
            }
          }
        })
        .catch((err) => {
          const error_obj = {
              state: 'error',
              stateOutlined: true,
              message: err
          }
          proxy.$alert(error_obj);
        })
        .finally(() => {
          onCancelCreateRoom();
        });
      } else {
        proxy.$alert({
            message: '초대할 친구를 선택해주세요.',
            state: 'warn',
            stateOutlined: true
        });
      }
    }
    const logout = function() {
      proxy.$router.replace('/login');
    }
    onMounted(() => {
      followingListSocket.onopen = function(event) {
          console.log('친구 목록 웹소켓 연결 성공');
      }
      followingListSocket.onmessage = function(event) {
          let followings = _.orderBy(JSON.parse(event.data), ['nickname'], ['asc']);
          followings = _.filter(followings, function(f) {
              return f.is_hidden === false && f.is_forbidden === false;
          });
          const self = _.find(followings, function(f) {
            return f.type === 'self';
          });
          const removeIdx = _.indexOf(followings, self);
          if (removeIdx !== -1) {
            followings.splice(_.indexOf(followings, self), 1);
            followings.unshift(self);
          }
          state.followings = followings;
      }
      followingListSocket.onclose = function(event) {
          console.log('following list close - ', event);
          proxy.$router.replace('/login');
      }
      followingListSocket.onerror = function(event) {
          console.log('following list error - ', event);
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
          console.log('chat room list close - ', event);
          proxy.$router.replace('/');
      }
      chatRoomListSocket.onerror = function(event) {
          console.log('chat room list error - ', event);
          proxy.$router.replace('/');
      }
    });
    return {
      state,
      onChangeChatMenuType,
      followingInfo,
      closeFollowingInfo,
      chatDetail,
      chatInfo,
      closeChatInfo,
      getDefaultProfileImage,
      onCancelAddUserProfile,
      onConfirmAddUserProfile,
      moveChatRoomDetail,
      searchProfile,
      getOneToOneBtnName,
      stopEvent,
      searchedFollowings,
      onClickProfileId,
      onCancelCreateRoom,
      onConfirmCreateRoom,
      logout,
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
        <div class="chat-menu-icon-top-layout">
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
        <div class="chat-menu-icon-down-layout">
          <!-- <ui-icon>notifications</ui-icon> -->
          <!-- <ui-icon>notifications_off</ui-icon> -->
          <ui-icon
            @click="state.showSettings = !state.showSettings"
            :style="{
              cursor: 'pointer'
            }"
          >settings</ui-icon>
        </div>
        <div
          v-show="state.showSettings" class="settings-popup" @click="logout()"
        >
          <div class="settings-popup-container">
            <div class="settings-popup-item">
              로그아웃
            </div>
          </div>
        </div>
      </div>
    </div>
    <div id="chat-header">
      <div class="chat-header-icon">
        <!-- <ui-icon 
          style="margin-right:10px;"
          v-tooltip="'친구 찾기'"
          aria-describedby="find-following-tooltip"
        >search
        </ui-icon> -->
        <ui-icon
          v-if="state.chatBodyListView['following']" 
          v-tooltip="'친구 추가'"
          aria-describedby="add-user-tooltip"
          @click="state.showAddUserPopup = !state.showAddUserPopup"
        >person_add_alt_1
        </ui-icon>
        <ui-icon
          v-else-if="state.chatBodyListView['chat']"
          v-tooltip="'채팅방 생성'"
          aria-describedby="add-user-tooltip"
          @click="state.showCreateRoomPopup = !state.showCreateRoomPopup"
        >add_comment
        </ui-icon>
      </div>
      <div v-show="state.showAddUserPopup" class="chat-header-btn-parent">
        <div class="add-user-popup">
          <div>
            <div class="add-user-popup-title">
                <span><b>친구 추가</b></span>
            </div>
            <div class="add-user-popup-input">
                <ui-textfield 
                  v-model="state.searchProfileIdentityId" 
                  outlined
                  @keypress.enter="searchProfile({'identity_id': state.searchProfileIdentityId})"
                >
                    <template #before>
                        <ui-textfield-icon>search</ui-textfield-icon>
                    </template>
                    친구 웹챗 ID
                </ui-textfield>
            </div>
            <div class="add-user-popup-result">
              <div v-if="state.searchedProfileIdentityId !== ''">
                <div v-if="state.addUserProfile !== null" class="add-user-container">
                  <div v-if="getDefaultProfileImage(state.addUserProfile.images) !== null" class="add-user-profile" :style="{
                      backgroundImage: 'url(' + getDefaultProfileImage(state.addUserProfile.images) + ')',
                      backgroundRepeat: 'no-repeat',
                      backgroundSize: 'cover',
                      backgroundPosition: 'center center',
                  }"></div>
                  <div v-else class="add-user-profile-default">
                      <p><ui-icon style="color: #b3e5fc" :size="48">person</ui-icon></p>
                  </div>
                  <p>{{ state.addUserProfile.nickname }}</p>
                </div>
                <div v-else>
                  <p>'{{ state.searchedProfileIdentityId }}'를 찾을 수 없습니다.</p>
                </div>
              </div>
            </div>
            <div class="add-user-btn">
              <div class="add-user-btn-container">
                <div>
                    <ui-button @click="onCancelAddUserProfile" style="margin-right: 5px;">취소</ui-button>
                </div>
                <div v-if="state.isAlreadyFollowing === false">
                    <ui-button raised @click="onConfirmAddUserProfile" style="margin-right: 5px;">친구 추가</ui-button>
                </div>
                <div v-else>
                  <ui-button raised @click="moveChatRoomDetail" style="margin-right: 5px;">{{ getOneToOneBtnName() }}</ui-button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
      <div v-show="state.showCreateRoomPopup" class="chat-header-btn-parent">
        <div class="invite-following-popup">
          <div>
            <div class="invite-following-popup-title">
              <span><b>채팅방 생성</b></span>
            </div>
            <div class="invite-following-popup-input">
              <ui-textfield v-model="state.searchFollowingNickname" outlined>
                <template #before>
                  <ui-textfield-icon>search</ui-textfield-icon>
                </template>
              </ui-textfield>
            </div>
            <div class="invite-following-popup-list">
              <div v-if="state.searchFollowingNickname === ''" class="following-list-container">
                <div v-for="following in state.followings" :key="following.id" class="following-list" @click="onClickProfileId(following.id)">
                  <div v-if="getDefaultProfileImage(following.files) !== null" class="following-profile" :style="{
                      backgroundImage: 'url(' + getDefaultProfileImage(following.files) + ')',
                      backgroundRepeat: 'no-repeat',
                      backgroundSize: 'cover',
                      backgroundPosition: 'center center',
                  }"></div>
                  <div v-else class="following-profile-default">
                    <p><ui-icon style="width: 100%; height: 100%; color: #b3e5fc">person</ui-icon></p>
                  </div>
                  <p>{{ following.nickname }}</p>
                  <input type="checkbox" v-model="state.selectedFollowingIds" :value="following.id" @click.stop="stopEvent" />
                </div>
              </div>
              <div v-else-if="searchedFollowings" class="following-list-container">
                <div v-for="following in searchedFollowings" :key="following.id" class="following-list" @click="onClickProfileId(following.id)">
                  <div v-if="getDefaultProfileImage(following.files) !== null" class="following-profile" :style="{
                      backgroundImage: 'url(' + getDefaultProfileImage(following.files) + ')',
                      backgroundRepeat: 'no-repeat',
                      backgroundSize: 'cover',
                      backgroundPosition: 'center center',
                  }"></div>
                  <div v-else class="following-profile-default">
                    <p><ui-icon style="width: 100%; height: 100%; color: #b3e5fc">person</ui-icon></p>
                  </div>
                  <p>{{ following.nickname }}</p>
                  <input type="checkbox" v-model="state.selectedFollowingIds" :value="following.id" @click.stop="stopEvent" />
                </div>
              </div>
              <div v-else class="following-list-container">검색 결과와 일치하는 친구가 없습니다.</div>
              <div class="invite-following-btn">
                <div class="invite-following-btn-container">
                  <div>
                    <ui-button @click="onCancelCreateRoom" style="margin-right: 5px;">취소</ui-button>
                  </div>
                  <div>
                    <ui-button raised @click="onConfirmCreateRoom" style="margin-right: 5px;">확인</ui-button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
    <div id="chat-body">
      <div class="chat-body-container">
        <FollowingListLayer
          v-if="state.chatBodyListView['following']"
          :followings="state.followings"
          @followingInfo="followingInfo"
        />
        <ChatListLayer
          v-if="state.chatBodyListView['chat']"
          :chatRooms="state.chatRooms"
          @chatDetail="chatDetail"
          @chatInfo="chatInfo"
        />
        <ChatDetailLayer
          v-if="state.chatBodyDetailView['chat']"
          :chatRoom="state.chatRoom"
          :chatRoomId="state.chatRoomId"
          @chatDetail="chatDetail"
          @followingInfo="followingInfo"
        />
        <FollowingInfoLayer
          v-if="state.chatBodyInfoView['following']"
          :userProfileId="state.userProfileId"
          @closeFollowingInfo="closeFollowingInfo"
          @moveChatRoomDetail="chatDetail"
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
.settings-popup {
  position: fixed;
  width: 150px;
  height: 50px;
  left: 75px;
  bottom: 40px;
  display: inline-block;
  background-color: #ffffff;
  border: 1px solid #e0e0e0;
  border-radius: 3%;
  box-shadow: 1px 2px 5px 0px #757575;
  box-sizing: border-box;
  z-index: 1;
}

.settings-popup:hover {
  background-color: #f5f5f5;
}

.settings-popup-container {
  margin: 0;
  width: 100%;
  height: 100%;
  display: flex; 
  flex-direction: column; 
  justify-content: center; 
  align-items: center;
  cursor: pointer;
}

.settings-popup-item {
  margin: 0;
}
.chat-header-btn-parent {
  position: relative;
  width: 100%;
}

.add-user-popup {
  position: absolute;
  width: 300px;
  height: 400px;
  right: 0;
  top: 10px;
  display: inline-block;
  background-color: #ffffff;
  border: 1px solid #e0e0e0;
  border-radius: 3%;
  box-shadow: 1px 2px 5px 0px #757575;
  box-sizing: border-box;
  z-index: 1;
}

.add-user-popup-title {
  height: 20px;
  padding: 15px;
  text-align: center;
}

.add-user-popup-input {
  height: 60px;
  padding: 10px;
}

.add-user-popup-input > div {
    width: 100%;
}

.add-user-popup-input > .material-icons {
    margin-left: 0;
}

.add-user-popup-result {
  width: 100%;
  height: 200px;
}

.add-user-popup-result > div {
  width: 100%;
  height: 100%;
}

.add-user-container {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
}

.add-user-profile {
  width: 130px;
  height: 130px;
  margin: 0;
  border-radius: 50%;
}
.add-user-profile-default {
  width: 130px; 
  height: 130px; 
  margin: 0;
  border-radius: 50%; 
  background-color: #81d4fa;
  display: flex;
  flex-direction: row;
  justify-content: center;
  align-items: center;
} 

.add-user-btn {
  width: 100%;
  height: calc(100% - 200px);
  text-align: center;
}

.add-user-btn-container {
  height: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
}

.invite-following-popup {
  position: absolute;
  width: 300px;
  height: 400px;
  right: 0;
  top: 10px;
  display: inline-block;
  background-color: #ffffff;
  border: 1px solid #e0e0e0;
  border-radius: 3%;
  box-shadow: 1px 2px 5px 0px #757575;
  box-sizing: border-box;
  z-index: 1;
}

.invite-following-popup > div {
    width: 100%;
    height: 100%;
}

.invite-following-popup-title {
    height: 20px;
    padding: 15px;
    text-align: center;
}

.invite-following-popup-input {
    height: 60px;
    padding: 10px;
}

.invite-following-popup-input > div {
    width: 100%;
}

.invite-following-popup-input > .material-icons {
    margin-left: 0;
}

.invite-following-popup-list {
    width: 100%;
    height: calc(100% - 130px);
}

.following-list-container {
    overflow: auto;
    height: 200px;
}

.invite-following-btn {
    width: 100%;
    height: calc(100% - 200px);
    text-align: center;
}

.invite-following-btn-container {
    height: 100%;
    display: flex;
    justify-content: center;
    align-items: center;
}

</style>
