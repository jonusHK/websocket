<script>
import { ref, reactive, watch, onMounted, getCurrentInstance, toRef, nextTick, onUpdated, computed } from 'vue';
import constants from '../constants';
import _ from 'lodash';
import { useEvent, useConfirm } from 'balm-ui';

const { VITE_SERVER_HOST } = import.meta.env;


export default {
    name: 'ChatDetailLayer',
    props: {
        chatRoom: Object,
    },
    setup (props, { emit }) {
        const { proxy } = getCurrentInstance();
        const uploadInput = ref(null);
        const confirmDialog = useConfirm();
        const state = reactive({
            loginProfileId: proxy.$store.getters['user/getProfileId'],
            followingsNotInRoom: [],
            room: toRef(props, 'chatRoom'),
            chatHistories: [],
            load: {
                offset: 0,
                limit: 50,
            },
            bottomFlag: true,
            uploadFiles: [],
            contents: '',
            showInvitePopup: false,
            searchFollowingNickname: '',
            selectedFollowingIds: [],
            scrollHeight: 0,
        });
        const ws = new WebSocket(`ws://localhost:8000/api/v1/chats/conversation/${state.loginProfileId}/${state.room.id}`);
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
            ws.send(JSON.stringify(data));
        }
        const onScrollChatHistories = function(e) {
            const { scrollHeight, scrollTop, clientHeight } = e.target;
            if (scrollTop + clientHeight + 1 >= scrollHeight) {
                state.bottomFlag = true;
            } else {
                state.bottomFlag = false;
                state.scrollHeight = scrollHeight;
                if (scrollTop === 0) {
                    loadMore();
                }
            }
        }
        const moveChatBodyPosition = function() {
            if (state.bottomFlag === true) {
                state.scrollHeight = 0;
            }
            const currentScrollHeight = window.$('.chat-detail-body-list').prop('scrollHeight');
            if (currentScrollHeight !== state.scrollHeight) {
                const height = window.$('.chat-detail-body-list').prop('scrollHeight') - state.scrollHeight;
                window.$('.chat-detail-body-list').scrollTop(height);
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
            const unreadCnt = state.room.user_profiles.length - obj.read_user_ids.length;
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
                ws.send(JSON.stringify(data));
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
                        window.$('#file-upload').val('');
                    }
                }
                fileReader.readAsDataURL(each);
            }
        }
        const send = function(e) {
            if (state.contents !== '') {
                const data = {
                    'type': 'message',
                    'data': {
                        'text': state.contents
                    }
                };
                ws.send(JSON.stringify(data));
                window.$('.chat-input-body').focus();
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
                    ws.send(JSON.stringify(data));     
                }
            });
        }
        const onCancelInviteFollowing = function() {
            state.showInvitePopup = false;
            state.searchFollowingNickname = '';
            state.selectedFollowingIds = [];
        }
        const onConfirmInviteFollowing = function() {
            if (state.selectedFollowingIds.length > 0) {
                const data = {
                    'type': 'invite',
                    'data': {
                        'target_profile_ids': state.selectedFollowingIds,
                    }
                }
                ws.send(JSON.stringify(data));
                onCancelInviteFollowing();
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
        onMounted(() => {
            ws.onopen = function(event) {
                console.log('채팅 웹소켓 연결 성공');
                const data = {
                    'type': 'lookup',
                    'data': {
                        'offset': state.load.offset,
                        'limit': state.load.limit,
                    }
                };
                ws.send(JSON.stringify(data));
                state.bottomFlag = true;
                window.$('.chat-input-body').focus();
            }
            ws.onmessage = function(event) {
                const json = JSON.parse(event.data);
                if (json.type === 'lookup') {
                    state.chatHistories = [...json.data.histories, ...state.chatHistories];
                } else if (json.type === 'update') {
                    const patchHistories = json.data.patch_histories;
                    if (patchHistories.length > 0 && state.chatHistories.length > 0) {
                        for (let i=0; i < patchHistories.length; i++) {
                            for (let j=state.chatHistories.length-1; j >=0; j--) {
                                if (state.chatHistories[j].id === patchHistories[i].id) {
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
                        emit('chatDetail', state.room.id);
                    }
                    state.chatHistories.push(json.data.history);
                }
            }
            ws.onclose = function(event) {
                console.log('chat socket close - ', event);
                ws.close();
                emit('exitChatRoom');
            }
            ws.onerror = function(event) {
                console.log('chat socket error - ', event);
                ws.close();
                emit('exitChatRoom');
            }
        })
        onUpdated(() => {
            const data = {
                'type': 'update',
                'data': {
                    'is_read': true
                }
            };
            ws.send(JSON.stringify(data));
            nextTick(() => {
                setTimeout(() => moveChatBodyPosition(), 50);
            });
        })
        const searchedFollowings = computed(() => {
            const searchedFollowings = _.filter(state.followingsNotInRoom, function(f) {
                return _.includes(f.profile.nickname, state.searchFollowingNickname);
            });
            return searchedFollowings;
        })
        watch(
            () => state.showInvitePopup,
            (cur, prev) => {
                if (cur === true) {
                    emit('chatDetail', state.room.id);
                    proxy.$axios.get(VITE_SERVER_HOST + `/users/relationship/${state.loginProfileId}/search`)
                    .then((res) => {
                        if (res.status === 200) {
                            state.followingsNotInRoom = _.filter(res.data.data, function(f) {
                                return !_.includes(_.map(state.room.user_profiles, 'id'), f.profile.id);
                            })
                        }
                    })
                }
            },
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
            send,
            exitRoom,
            onCancelInviteFollowing,
            onConfirmInviteFollowing,
            stopEvent,
            searchedFollowings,
        }
    }
}
</script>

<template>
    <div class="chat-detail-body">
        <div class="chat-detail-body-list" v-if="state.chatHistories" @scroll="onScrollChatHistories">
            <div v-for="obj in state.chatHistories" :key="obj.id" class="chat-histories">
                <div v-if="obj.type !== 'notice'" class="chat-history">
                    <div v-if="getUserProfileImageByChat(obj) !== null" class="chat-profile" @click="onClickProfileId(obj.user_profile_id)" :style="{
                        backgroundImage: 'url(' + getDefaultProfileImageByChat(obj) + ')',
                        backgroundRepeat: 'no-repeat',
                        backgroundSize: 'cover',
                        backgroundPosition: 'center center',
                    }"></div>
                    <div v-else class="chat-profile-default">
                        <p><ui-icon style="width: 100%; height: 100%; color: #b3e5fc">person</ui-icon></p>
                    </div>
                    <div>
                        <div class="chat-profile-info-meta">
                            <p><b>{{ getChatUserProfileNickname(obj) }}</b></p>
                            <p>{{ getChatHistoryCreated(obj) }}</p>
                            <p>{{ getUnreadCnt(obj) }}</p>
                        </div>
                        <div v-if="obj.is_active === true">
                            <p v-if="obj.contents !== null">{{ obj.contents }}</p>
                            <div v-if="obj.files.length">
                                <div v-for="file in obj.files" :key="file.chat_history_id" :class="{'file-multiple-preview': obj.files.length > 1, 'file-preview': obj.files.length == 1}">
                                    <!-- TODO 유효기간 만료 시, 처리 -->
                                    <img v-if="file.content_type.startsWith('image')" :src="file.url" />
                                </div>
                            </div>
                        </div>
                        <div v-else style="text-align: center;">
                            <p>삭제된 메시지입니다.</p>
                        </div>
                    </div>
                </div>
                <div v-else style="text-align: center;">
                    <p>{{ obj.contents }}</p>
                </div>
            </div>
        </div>
        <div class="chat-input-parent">
            <div
                v-show="state.showInvitePopup"
                class="invite-following-popup"
            >
                <div>
                    <div class="invite-following-popup-title">
                        <span><b>대화상대 선택</b></span>
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
                                    <ui-button @click="onCancelInviteFollowing" style="margin-right: 5px;">취소</ui-button>
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
                    @keypress.enter="send"
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
                                @click="state.showInvitePopup = true"
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
                        <ui-button outlined @click="send" style="color: #757575;">전송</ui-button>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped>
.chat-detail-body {
  width: 100%;
  height: 100%;
  border-left: 1px solid #e0e0e0;
}

.chat-detail-body-list {
  width: 100%;
  height: calc(100% - 150px);
  overflow: auto;
}

.chat-histories {
    padding: 15px;
    cursor: pointer;
}

.chat-histories:hover {
    background-color: #f5f5f5;
}

.chat-histories p {
    margin: 0;
}

.chat-history {
    display: flex;
    flex-direction: row;
    justify-content: flex-start;
    align-items: flex-start;
}

.chat-profile-default {
    width: 40px;
    height: 40px; 
    margin: 0 10px 0 0;
    border-radius: 10%; 
    background-color: #81d4fa;
    display: flex;
    flex-direction: row;
    justify-content: center;
    align-items: center;
}

.chat-profile {
    width: 40px; 
    height: 40px; 
    margin: 0 10px 0 0; 
    border-radius: 50%; 
}

.chat-profile-info-meta {
    margin-bottom: 7px;
    display: flex;
    flex-direction: row;
    align-items: center;
}

.chat-profile-info-meta p {
    margin-right: 10px;
}

.chat-profile-info-meta p:nth-child(2) {
    font-size: 13px;
    color: #757575;
}

.chat-profile-info-meta p:nth-child(3) {
    font-weight: bold;
    font-size: 13px;
    color: #f9a825;
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
    width: 90%;
    height: 400px;
    left: -5px;
    bottom: 150px;
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
    width: 200px;
    margin-right: 3px;
}
</style>