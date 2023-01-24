<script>
import { reactive, watch, onMounted, getCurrentInstance, toRef, nextTick, onUpdated, computed } from 'vue';
import constants from '../constants';
import _ from 'lodash';

const { VITE_SERVER_HOST } = import.meta.env;


export default {
    name: 'ChatDetailLayer',
    props: {
        chatRoom: Object,
    },
    setup (props, { emit }) {
        const { proxy } = getCurrentInstance();
        const state = reactive({
            room: toRef(props, 'chatRoom'),
            chatHistories: [],
            load: {
                offset: 0,
                limit: 15,
            },
            newMessage: false,
            chatBodyScrollHeight: 0,
            bottomFlag: true,
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
            state.newMessage = false;
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
            if (state.bottomFlag === true) {
                state.chatBodyScrollHeight = 0;
            }
            if (state.bottomFlag === true || state.newMessage === false) {
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
            return state.room.user_profiles.length - obj.read_user_ids.length;
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
                moveChatBodyPosition();
            }
            ws.onmessage = function(event) {
                const json = JSON.parse(event.data);
                if (json.type === 'message') {
                    state.newMessage = true;
                    state.chatHistories.push(json.data.history);
                } else if (json.type === 'lookup') {
                    state.chatHistories = [...json.data.histories, ...state.chatHistories];
                } else if (json.type === 'file') {
                    state.chatHistories.push(json.data.history);
                } else if (json.type === 'invite') {

                } else if (json.type === 'update') {
                    const patchHistories = json.data.patch_histories;
                    if (patchHistories !== [] && state.chatHistories !== []) {
                        for (const h of state.chatHistories) {
                            for (const p of patchHistories) {
                                if (h.id === p.id) {
                                    h.is_active = p.is_active;
                                    h.read_user_ids = p.read_user_ids;
                                    break;
                                }
                            }
                        }
                    }
                } else if (json.type === 'terminate') {

                }
            }
            ws.onclose = function(event) {
                console.log('close - ', event);
                proxy.$router.replace('/login');
            }
            ws.onerror = function(event) {
                console.log('error - ', event);
                proxy.$router.replace('/login');
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
            state,
            onClickProfile,
            getUserProfileImage,
            getDefaultProfileImage,
            onScrollChatHistories,
            moveChatBodyPosition,
            getChatUserProfileNickname,
            getChatHistoryCreated,
            getUnreadCnt,
        }
    }
}
</script>

<template>
    <div class="chat-body-list chat-detail-body-list" v-if="state.chatHistories" @scroll="onScrollChatHistories">
        <div v-for="obj in state.chatHistories" :key="obj.id" class="chat-list">
            <div>
                <div v-if="getUserProfileImage(obj) !== null" class="chat-profile" @click="onClickProfile(obj)" :style="{
                    backgroundImage: 'url(' + getDefaultProfileImage(obj) + ')',
                    backgroundRepeat: 'no-repeat',
                    backgroundSize: 'cover'
                }"></div>
                <div v-else class="chat-profile-default">
                    <p><ui-icon style="width: 100%; height: 100%; color: #b3e5fc">person</ui-icon></p>
                </div>
            </div>
            <div>
                <div class="chat-profile-info-meta">
                    <p><b>{{ getChatUserProfileNickname(obj) }}</b></p>
                    <p>{{ getChatHistoryCreated(obj) }}</p>
                    <p>{{ getUnreadCnt(obj) }}</p>
                </div>
                <div>
                    <p v-if="obj.contents !== null">{{ obj.contents }}</p>
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped>
.chat-list {
    display: flex;
    flex-direction: row;
    justify-content: flex-start;
    align-items: flex-start;
    padding: 15px;
    cursor: pointer;
}

.chat-list:hover {
    background-color: #f5f5f5;
}

.chat-list p {
    margin: 0;
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
</style>