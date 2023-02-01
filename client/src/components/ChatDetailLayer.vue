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
            room: toRef(props, 'chatRoom'),
            chatHistories: [],
            load: {
                offset: 0,
                limit: 50,
            },
            newMessage: false,
            onScroll: false,
            chatBodyScrollHeight: 0,
            chatBodyClientHeight: 0,
            bottomFlag: true,
            uploadFiles: [],
            contents: '',
            showInvitePopup: false,
        });
        const ws = new WebSocket(`ws://localhost:8000/api/v1/chats/conversation/${proxy.$store.getters['user/getProfileId']}/${state.room.id}`);
        const onClickProfile = function(obj) {
            emit('followingInfo', obj.user_profile_id);
        }
        const getUserProfileImage = function(obj) {
            const profiles = _.filter(state.room.user_profiles, function(p) {
                return p.id === obj.user_profile_id;
            });
            return profiles !== [] ? profiles[0].image : null;
        }
        const getDefaultProfileImage = function(obj) {
            const profiles = _.filter(state.room.user_profiles, function(p) {
                return p.id === obj.user_profile_id;
            });
            if (profiles !== []) {
                if (profiles[0].image === null) {
                    return null;
                }
                return profiles[0].image.url;
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
            state.onScroll = true;
            const { scrollHeight, scrollTop, clientHeight } = e.target;
            state.chatBodyScrollHeight = scrollHeight;
            if (scrollTop + clientHeight === scrollHeight) {
                state.bottomFlag = true;
            } else {
                state.bottomFlag = false;
                if (scrollTop === 0) {
                    loadMore();
                }
            }
        }
        const moveChatBodyPosition = function() {
            if (state.bottomFlag === true || state.onScroll === true) {
                if (state.bottomFlag === true) {
                    state.chatBodyScrollHeight = 0;
                }
                else if (state.newMessage === true) {
                    return;
                }
                state.chatBodyScrollHeight = window.$('.chat-detail-body-list').prop('scrollHeight') - state.chatBodyScrollHeight;
                window.$('.chat-detail-body-list').scrollTop(state.chatBodyScrollHeight);
            }
        }
        const getChatUserProfileNickname = function(obj) {
            const profiles = _.filter(state.room.user_profiles, function(p) {
                return p.id === obj.user_profile_id;
            });
            if (profiles !== []) {
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
        const send = function() {
            if (state.contents !== '') {
                const data = {
                    'type': 'message',
                    'data': {
                        'text': state.contents
                    }
                };
                ws.send(JSON.stringify(data));
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
            }
            ws.onmessage = function(event) {
                const json = JSON.parse(event.data);
                if (json.type === 'message') {
                    state.newMessage = true;
                    state.chatHistories.push(json.data.history);
                } else if (json.type === 'lookup') {
                    state.chatHistories = [...json.data.histories, ...state.chatHistories];
                } else if (json.type === 'file') {
                    state.newMessage = true;
                    state.chatHistories.push(json.data.history);
                } else if (json.type === 'invite') {

                } else if (json.type === 'update') {
                    const patchHistories = json.data.patch_histories;
                    if (patchHistories !== [] && state.chatHistories !== []) {
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
                } else if (json.type === 'terminate') {
                    state.newMessage = true;
                    state.chatHistories.push(json.data.history);
                }
            }
            ws.onclose = function(event) {
                console.log('close - ', event);
                proxy.$router.replace('/');
            }
            ws.onerror = function(event) {
                console.log('error - ', event);
                proxy.$router.replace('/');
            }
        })
        onUpdated(() => {
            moveChatBodyPosition();
            const data = {
                'type': 'update',
                'data': {
                    'is_read': true
                }
            };
            ws.send(JSON.stringify(data));
        })
        return {
            uploadInput,
            state,
            onClickProfile,
            getUserProfileImage,
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
        }
    }
}
</script>

<template>
    <div class="chat-detail-body">
        <div class="chat-detail-body-list" v-if="state.chatHistories" @scroll="onScrollChatHistories">
            <div v-for="obj in state.chatHistories" :key="obj.id" class="chat-histories">
                <div v-if="obj.type !== 'notice'" class="chat-history">
                    <div v-if="getUserProfileImage(obj) !== null" class="chat-profile" @click="onClickProfile(obj)" :style="{
                        backgroundImage: 'url(' + getDefaultProfileImage(obj) + ')',
                        backgroundRepeat: 'no-repeat',
                        backgroundSize: 'cover'
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
                <p>대화상대 초대</p>
            </div>
            <div class="chat-input-child">
                <textarea
                    v-model="state.contents"
                    class="chat-input-body"
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
    bottom: 152px;
    display: inline-block;
    opacity: 1;
    border: 1px solid #e0e0e0;
    border-radius: 10%;
    box-shadow: 1px 2px 5px 0px #757575;
    box-sizing: border-box;
    z-index: 1;
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