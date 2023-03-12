<script>
import { ref, reactive, watch, onMounted, onUnmounted, getCurrentInstance, toRef, nextTick, computed } from 'vue';
import _ from 'lodash';
import { useConfirm } from 'balm-ui';

const { VITE_SERVER_HOST, VITE_SERVER_WEBSOCKET_HOST } = import.meta.env;

export default {
    name: 'ChatDetailLayer',
    props: {
        chatRoom: Object,
        chatRoomId: Number,
    },
    setup (props, { emit }) {
        const { proxy } = getCurrentInstance();
        const uploadInput = ref(null);
        const confirmDialog = useConfirm();
        const state = reactive({
            loginProfileId: proxy.$store.getters['user/getProfileId'],
            roomId: toRef(props, 'chatRoomId'),
            room: {},
            chatHistories: [],
            load: {
                offset: 0,
                limit: 50,
            },
            bottomFlag: true,
            moveFlag: true,
            uploadFiles: [],
            contents: '',
            showInvitePopup: false,
            searchFollowingNickname: '',
            selectedFollowingIds: [],
            followingsNotInRoom: [],
            scrollHeight: 0,
            pingInterval: null,
        });
        proxy.$axios.get(VITE_SERVER_HOST + `/v1/chats/room/${state.loginProfileId}/${state.roomId}`)
        .then((res) => {
            if (res.status === 200) {
                state.room = res.data.data;
            }
        })
        .catch((err) => {
            proxy.$alert({
                state: 'error',
                stateOutlined: true,
                message: err.response.data.message,
            });
            if (_.includes(['PERMISSION_DENIED', 'UNAUTHORIZED'], err.response.data.code)) {
                proxy.$router.replace('/login');
            }
        });
        const wsUrl = ref(`${VITE_SERVER_WEBSOCKET_HOST}/v1/chats/conversation/${state.loginProfileId}/${state.roomId}`);
        const isConnected = ref(false);
        const ws = ref(new WebSocket(wsUrl.value));
        const wsSend = function(data) {
            if (ws.value.readyState === WebSocket.OPEN) {
                ws.value.send(JSON.stringify(data));
            }
        }
        const initData = function() {
            state.load = {
                offset: 0,
                limit: 50,
            };
            state.bottomFlag = true;
            state.uploadFiles = [];
            state.chatHistories = [];
            state.contents = '';
            state.showInvitePopup = false;
            state.searchFollowingNickname = '';
            state.selectedFollowingIds = [];
            state.scrollHeight = 0;
        }
        const onClickProfileId = function(followingId) {
            emit('followingInfo', followingId);
        }
        const getUserProfileImageByChat = function(obj) {
            const profiles = _.filter(state.room.user_profiles, function(p) {
                return p.id === obj.user_profile_id;
            });
            return profiles.length > 0 ? profiles[0].image : null;
        }
        const getDefaultProfileImageByChat = function(obj) {
            const profiles = _.filter(state.room.user_profiles, function(p) {
                return p.id === obj.user_profile_id;
            });
            if (profiles.length > 0) {
                if (profiles[0].image === null) {
                    return null;
                }
                return profiles[0].image.url;
            }
            return null;
        }
        const getDefaultProfileImage = function(obj) {
            if (obj.profile.images.length > 0) {
                for (const i in obj.profile.images) {
                    const image = obj.profile.images[i];
                    // type -> 1: 프로필 이미지 2: 배경 이미지
                    if (image.type === 1 && image.is_default === true) {
                        return image.url;
                    }
                }
                return null;
            }
            return null;
        }
        const loadMore = function() {
            state.load.offset = state.load.offset + state.load.limit;
            const data = {
                'type': 'lookup',
                'data': {
                    'offset': state.load.offset,
                    'limit': state.load.limit,
                }
            };
            wsSend(data);
        }
        const onScrollChatHistories = function(e) {
            const { scrollHeight, scrollTop, clientHeight } = e.target;
            if (scrollTop + clientHeight + 1 >= scrollHeight) {
                state.bottomFlag = true;
            } else {
                state.bottomFlag = false;
                state.scrollHeight = scrollHeight;
                if (scrollTop === 0) {
                    state.moveFlag = true;
                    loadMore();
                } else {
                    state.moveFlag = false;
                }
            }
        }
        const moveChatBodyPosition = function() {
            const currentScrollHeight = document.querySelector('.chat-detail-body-list').scrollHeight;
            if (state.bottomFlag || (state.moveFlag && currentScrollHeight !== state.scrollHeight)) {
                if (state.bottomFlag) {
                    state.scrollHeight = 0;
                }
                const height = currentScrollHeight - state.scrollHeight;
                document.querySelector('.chat-detail-body-list').scrollTop = height;
            }
        }
        const getChatUserProfileNickname = function(obj) {
            const profiles = _.filter(state.room.user_profiles, function(p) {
                return p.id === obj.user_profile_id;
            });
            if (profiles.length > 0) {
                return profiles[0].nickname;
            } else {
                return '알 수 없는 유저'
            }
        }
        const getChatHistoryCreated = function(obj) {
            if (obj === null) {
                return null;
            }
            const dt = proxy.$dayjs.unix(obj.timestamp);
            return dt.format('A h:mm');
        }
        const getUnreadCnt = function(obj) {
            const read_user_profiles = state.room.user_profiles.filter(p => obj.read_user_ids.includes(p.id));
            const unreadCnt = state.room.user_profiles.length - read_user_profiles.length;
            return unreadCnt > 0 ? unreadCnt : null;
        }
        const sendFiles = function() {
            if (state.uploadFiles.length > 0) {
                const data = {
                    'type': 'file',
                    'data': {
                        'files': state.uploadFiles.map(elem => {
                            elem.content = elem.content.split(',')[1]
                            return elem
                        })
                    }
                }
                wsSend(data);
                state.bottomFlag = true;
            }
        }
        const onInputFile = function() {
            for (const each of uploadInput.value.files) {
                const fileReader = new FileReader();
                fileReader.onload = function(event) {
                    state.uploadFiles.push({
                        content: event.target.result,
                        filename: each.name,
                        content_type: each.type
                    })
                    if (state.uploadFiles.length === uploadInput.value.files.length) {
                        sendFiles();
                        state.uploadFiles = [];
                        document.querySelector('#file-upload').value = '';
                    }
                }
                fileReader.readAsDataURL(each);
            }
        }
        const sendMessage = function(e) {
            if (state.contents !== '') {
                const data = {
                    'type': 'message',
                    'data': {
                        'text': state.contents
                    }
                };
                wsSend(data);
                state.bottomFlag = true;
                document.querySelector('.chat-input-body').focus();
                state.contents = '';
                if (e !== undefined) {
                    e.preventDefault();
                }
            }
        }
        const exitRoom = function() {
            confirmDialog({
                message: '방을 나가시겠습니까?',
                acceptText: '네',
                cancelText: '아니요'
            }).then((result) => {
                if (result) {
                    const data = {
                        'type': 'terminate'
                    };
                    wsSend(data);
                }
            });
        }
        const onConfirmInviteFollowing = function() {
            if (state.selectedFollowingIds.length > 0) {
                const data = {
                    'type': 'invite',
                    'data': {
                        'target_profile_ids': state.selectedFollowingIds,
                    }
                }
                wsSend(data);
                state.showInvitePopup = false;
            } else {
                proxy.$alert({
                    message: '초대할 친구를 선택해주세요.',
                    state: 'warn',
                    stateOutlined: true
                });
            }
        }
        const stopEvent = function(e) {
            e.stopPropagation();
        }
        const connectWebsocket = function() {
            // Send a ping message every 30 seconds
            state.pingInterval = setInterval(() => {
                const data = {
                    'type': 'ping'
                };
                wsSend(data);
            }, 30000);

            ws.value.onopen = function(event) {
                console.log('채팅 웹소켓 연결 성공');
                isConnected.value = true;
                const data = {
                    'type': 'lookup',
                    'data': {
                        'offset': state.load.offset,
                        'limit': state.load.limit,
                    }
                };
                wsSend(data);
                state.bottomFlag = true;
                nextTick(() => {
                    document.querySelector('.chat-input-body').focus();
                })
            }
            ws.value.onmessage = function(event) {
                try {
                    const json = JSON.parse(event.data);
                    if (json.type === 'lookup') {
                        state.chatHistories = [...json.data.histories, ...state.chatHistories];
                    } else if (json.type === 'update') {
                        const patchHistories = json.data.patch_histories;
                        if (patchHistories.length > 0 && state.chatHistories.length > 0) {
                            for (let i=0; i < patchHistories.length; i++) {
                                for (let j=state.chatHistories.length-1; j >=0; j--) {
                                    if (state.chatHistories[j].redis_id === patchHistories[i].redis_id) {
                                        state.chatHistories[j].is_active = patchHistories[i].is_active;
                                        state.chatHistories[j].read_user_ids = patchHistories[i].read_user_ids;
                                        break;
                                    }
                                }
                            }
                        }
                    } else {
                        // type => message, file, invite, terminate
                        if (_.includes(['invite', 'terminate'], json.type) === true) {
                            refreshRoom();
                        }
                        state.chatHistories.push(json.data.history);
                    }

                    if (_.includes(['lookup', 'message', 'file', 'invite'], json.type)) {
                    // 스크롤 이동
                    nextTick(() => {
                        setTimeout(() => moveChatBodyPosition(), 50);
                    })
                }
                } catch (e) {}
            }
            ws.value.onclose = function(event) {
                console.log('chat socket close - ', event);
                isConnected.value = false;
                clearInterval(state.pingInterval);
                if (_.includes([1008, 1006], event.code)) {
                    proxy.$alert({
                        state: 'error',
                        stateOutlined: true,
                        message: event.reason || '연결이 끊어습니다.',
                    });
                    proxy.$router.replace('/login');
                    
                }
            }
            ws.value.onerror = function(event) {
                console.log('chat socket error - ', event);
                isConnected.value = false;
                clearInterval(state.pingInterval);
                if (_.includes([1008, 1006], event.code)) {
                    proxy.$alert({
                        state: 'error',
                        stateOutlined: true,
                        message: event.reason || '연결이 끊어습니다.',
                    });
                    proxy.$router.replace('/login');
                }
            }
        }
        const getUserCnt = function() {
            return state.room.user_profiles.length > 2 ? state.room.user_profiles.length : null;
        }
        const refreshRoom = function() {
            proxy.$axios.get(VITE_SERVER_HOST + `/v1/chats/room/${state.loginProfileId}/${state.roomId}`)
                .then((res) => {
                    if (res.status === 200) {
                        state.room = res.data.data;
                    }
                })
                .catch((err) => {
                    proxy.$alert({
                        state: 'error',
                        stateOutlined: true,
                        message: err.response.data.message,
                    });
                    if (_.includes(['PERMISSION_DENIED', 'UNAUTHORIZED'], err.response.data.code)) {
                        proxy.$router.replace('/login');
                    }
                });
        }
        onMounted(() => {
            connectWebsocket();
        })
        onUnmounted(() => {
            if (ws.value.readyState === WebSocket.OPEN) {
                clearInterval(state.pingInterval);
                ws.value.close(1000);
            }
        })
        const searchedFollowings = computed(() => {
            const searchedFollowings = _.filter(state.followingsNotInRoom, function(f) {
                return _.includes(f.profile.nickname, state.searchFollowingNickname);
            });
            return searchedFollowings;
        })
        watch(
            () => state.showInvitePopup,
            (cur) => {
                if (cur) {
                    refreshRoom();
                    proxy.$axios.get(VITE_SERVER_HOST + `/v1/users/relationship/${state.loginProfileId}/search`)
                        .then((res) => {
                            if (res.status === 200) {
                                state.followingsNotInRoom = _.filter(res.data.data, function(f) {
                                    return !_.includes(_.map(state.room.user_profiles, 'id'), f.profile.id);
                                })
                            }
                        })
                        .catch((err) => {
                            proxy.$alert({
                                state: 'error',
                                stateOutlined: true,
                                message: err.response.data.message,
                            });
                            if (_.includes(['PERMISSION_DENIED', 'UNAUTHORIZED'], err.response.data.code)) {
                                proxy.$router.replace('/login');
                            }
                        });
                } else {
                    state.searchFollowingNickname = '';
                    state.selectedFollowingIds = [];
                }
            },
        )
        watch(
            () => props.chatRoomId,
            (cur) => {
                initData();
                refreshRoom();
                wsUrl.value = `${VITE_SERVER_WEBSOCKET_HOST}/v1/chats/conversation/${state.loginProfileId}/${cur}`;
            },
        )
        watch(
            () => wsUrl.value,
            (newUrl) => {
                if (ws.value && ws.value.readyState === WebSocket.OPEN) {
                    ws.value.close(1000);
                }
                let retryCnt = 5;
                while (retryCnt >= 0) {
                    try {
                        ws.value = new WebSocket(newUrl);
                        break;
                    } catch (e) {
                        retryCnt -= 1;
                        sleep(200);
                    }
                }
                
                connectWebsocket();
            }
        )
        return {
            uploadInput,
            state,
            onClickProfileId,
            getUserProfileImageByChat,
            getDefaultProfileImageByChat,
            getDefaultProfileImage,
            onScrollChatHistories,
            moveChatBodyPosition,
            getChatUserProfileNickname,
            getChatHistoryCreated,
            getUnreadCnt,
            onInputFile,
            sendFiles,
            sendMessage,
            exitRoom,
            onConfirmInviteFollowing,
            stopEvent,
            getUserCnt,
            searchedFollowings,
            isConnected,
        }
    }
}
</script>

<template>
    <div v-if="isConnected" class="chat-detail-body">
        <div class="chat-body-info-summary">
            <div>
                <p><b>{{ state.room.name }}</b><span class="chat-room-info-user-cnt">&nbsp;&nbsp;{{ getUserCnt() }}</span></p>
            </div>
        </div>
        <div class="chat-detail-body-list" v-if="state.chatHistories.length > 0" @scroll="onScrollChatHistories">
            <div v-for="obj in state.chatHistories" :key="obj.redis_id" class="chat-histories-container">
                <div v-if="obj.type !== 'notice'" class="chat-history-container">
                    <div v-if="getUserProfileImageByChat(obj) !== null" class="chat-profile-container" :style="{
                        backgroundImage: 'url(' + getDefaultProfileImageByChat(obj) + ')',
                        backgroundRepeat: 'no-repeat',
                        backgroundSize: 'cover',
                        backgroundPosition: 'center center',
                    }" @click="onClickProfileId(obj.user_profile_id)"></div>
                    <div v-else class="chat-profile-default-container" @click="onClickProfileId(obj.user_profile_id)">
                        <p><ui-icon style="width: 100%; height: 100%; color: #b3e5fc">person</ui-icon></p>
                    </div>
                    <div class="chat-contents-container">
                        <div class="chat-profile-meta">
                            <span><b>{{ getChatUserProfileNickname(obj) }}</b></span>
                            <span>{{ getChatHistoryCreated(obj) }}</span>
                            <span>{{ getUnreadCnt(obj) }}</span>
                        </div>
                        <div v-if="obj.is_active === true" class="chat-contents">
                            <p v-if="obj.contents !== null">{{ obj.contents }}</p>
                            <div v-if="obj.files.length">
                                <div 
                                    v-for="file in obj.files" 
                                    :key="file.chat_history_id" 
                                    :class="{
                                        'file-multiple-preview': obj.files.length > 1, 
                                        'file-preview': obj.files.length == 1
                                    }"
                                >
                                    <!-- TODO 유효기간 만료 시, 처리 -->
                                    <img v-if="file.content_type.startsWith('image')" :src="file.url" />
                                </div>
                            </div>
                        </div>
                        <div v-else class="chat-notice-container">
                            <p>삭제된 메시지입니다.</p>
                        </div>
                    </div>
                </div>
                <div v-else class="chat-notice-container">
                    <p>{{ obj.contents }}</p>
                </div>
            </div>
        </div>
        <div class="chat-detail-body-list" v-else></div>
        <div class="chat-input-parent">
            <div
                v-show="state.showInvitePopup"
                class="invite-following-popup"
            >
                <div>
                    <div class="invite-following-popup-title">
                        <span><b>대화상대 초대</b></span>
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
                            <div v-for="following in state.followingsNotInRoom" :key="following.profile.id" class="following-list" @click="onClickProfileId(following.profile.id)">
                                <div v-if="getDefaultProfileImage(following) !== null" class="following-profile" :style="{
                                    backgroundImage: 'url(' + getDefaultProfileImage(following) + ')',
                                    backgroundRepeat: 'no-repeat',
                                    backgroundSize: 'cover',
                                    backgroundPosition: 'center center',
                                }"></div>
                                <div v-else class="following-profile-default">
                                    <p><ui-icon style="width: 100%; height: 100%; color: #b3e5fc">person</ui-icon></p>
                                </div>
                                <p>{{ following.profile.nickname }}</p>
                                <input type="checkbox" v-model="state.selectedFollowingIds" :value="following.profile.id" @click.stop="stopEvent" />
                            </div>
                        </div>
                        <div v-else-if="searchedFollowings" class="following-list-container">
                            <div v-for="following in searchedFollowings" :key="following.profile.id" class="following-list" @click="onClickProfileId(following.profile.id)">
                                <div v-if="getDefaultProfileImage(following) !== null" class="following-profile" :style="{
                                    backgroundImage: 'url(' + getDefaultProfileImage(following) + ')',
                                    backgroundRepeat: 'no-repeat',
                                    backgroundSize: 'cover',
                                    backgroundPosition: 'center center',
                                }"></div>
                                <div v-else class="following-profile-default">
                                    <p><ui-icon style="width: 100%; height: 100%; color: #b3e5fc">person</ui-icon></p>
                                </div>
                                <p>{{ following.profile.nickname }}</p>
                                <input type="checkbox" v-model="state.selectedFollowingIds" :value="following.profile.id" @click.stop="stopEvent" />
                            </div>
                        </div>
                        <div v-else class="following-list-container">검색 결과와 일치하는 친구가 없습니다.</div>
                        <div class="invite-following-btn">
                            <div class="invite-following-btn-container">
                                <div>
                                    <ui-button @click="state.showInvitePopup = false" style="margin-right: 5px;">취소</ui-button>
                                </div>
                                <div>
                                    <ui-button raised @click="onConfirmInviteFollowing" style="margin-right: 5px;">확인</ui-button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            <div class="chat-input-child">
                <textarea
                    v-model="state.contents"
                    class="chat-input-body"
                    @keypress.enter="sendMessage"
                ></textarea>
                <div class="chat-input-menu">
                    <div>
                        <div class="chat-input-icon">
                            <label for="file-upload" class="icons-preview-code upload-icon">
                                <ui-icon 
                                    v-tooltip="'파일 업로드'"
                                    aria-describedby="file-upload-tooltip"
                                >upload
                                </ui-icon>
                            </label>
                            <ui-icon
                                class="invite-following"
                                @click="state.showInvitePopup = !state.showInvitePopup"
                                v-tooltip="'대화상대 초대'"
                                aria-describedby="invite-following-tooltip"
                            >add_box
                            </ui-icon>
                            <ui-icon
                                class="exit-room-icon" 
                                @click="exitRoom"
                                v-tooltip="'채팅방 나가기'"
                                aria-describedby="exit-room-tooltip"
                            >logout
                            </ui-icon>
                        </div>
                        <input
                            v-show="false"
                            type="file"
                            id="file-upload"
                            multiple="multiple"
                            accept="image/*"
                            @change="onInputFile"
                            ref="uploadInput"
                        />
                        <ui-button outlined @click="sendMessage" style="color: #757575;">전송</ui-button>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped>
.chat-detail-body {
  width: 100%;
  min-width: 300px;
  height: 100%;
  border-left: 1px solid #e0e0e0;
}

.chat-detail-body-list {
  width: 100%;
  height: calc(100% - 200px);
  overflow: auto;
}

.chat-histories-container {
    padding: 15px;
    cursor: pointer;
}

.chat-histories-container:hover {
    background-color: #f5f5f5;
}

.chat-histories-container p {
    margin: 0;
}

.chat-history-container {
    display: flex;
    flex-direction: row;
    justify-content: flex-start;
    align-items: flex-start;
}

.chat-profile-default-container {
    height: 40px;
    flex-basis: 40px;
    flex-grow: 0;
    flex-shrink: 0;
    margin: 0 10px 0 0;
    border-radius: 10%; 
    background-color: #81d4fa;
    display: flex;
    flex-direction: row;
    justify-content: center;
    align-items: center;
}

.chat-profile-container {
    height: 40px;
    flex-basis: 40px;
    flex-grow: 0;
    flex-shrink: 0;
    margin: 0 10px 0 0; 
    border-radius: 50%; 
}

.chat-contents-container {
    flex-basis: 100%;
    flex-grow: 1;
    flex-shrink: 1;
}

.chat-profile-meta {
    margin-bottom: 7px;
}

.chat-profile-meta span {
    margin-right: 10px;
}

.chat-profile-meta span:nth-child(2) {
    font-size: 13px;
    color: #757575;
}

.chat-profile-meta span:nth-child(3) {
    font-weight: bold;
    font-size: 13px;
    color: #f9a825;
}

.chat-notice-container {
    height: 45px;
    color: #757575;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
}

.chat-input-parent {
    position: relative;
    width: 100%;
    height: 150px;
    border: 1px solid #e0e0e0;
    background-color: #ffffff;
}

.chat-input-child {
    position: absolute;
    width: 100%;
}

.chat-input-body {
    width: calc(100% - 6px);
    font-size: 15px;
    font-family: '굴림', Gulim, Arial, sans-serif;
    height: 90px;
    border: none;
    resize: none;
}

.chat-input-menu {
    padding: 10px;
}

.chat-input-menu > div {
    display: flex;
    justify-content: space-between;
}

.chat-input-icon {
    display: flex;
    flex-direction: row;
    align-items: center;
}

.chat-room-info-user-cnt {
    color: #9e9e9e;
}

.upload-icon {
    display: flex;
    flex-direction: row;
    align-items: center;
    cursor: pointer;
    color: #757575;
    margin-right: 10px;
}

.invite-following {
    cursor: pointer;
    color: #757575;
    margin-right: 10px;
}

.invite-following-popup {
    position: absolute;
    width: 300px;
    height: 400px;
    left: 10px;
    bottom: 50px;
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

.exit-room-icon {
    cursor: pointer;
    color: #757575;
}

.file-multiple-preview > img {
    height: 200px;
    margin-right: 3px;
}

.file-preview > img {
    height: 200px;
    margin-right: 3px;
}
</style>