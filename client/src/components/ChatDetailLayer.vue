<script>
import { reactive, watch, onMounted, getCurrentInstance, toRef, nextTick, onUpdated } from 'vue';
import constants from '../constants';

const { VITE_SERVER_HOST } = import.meta.env;


export default {
    name: 'ChatDetailLayer',
    props: {
        chatRoomId: Number,
    },
    setup (props, { emit }) {
        const { proxy } = getCurrentInstance();
        const state = reactive({
            roomId: toRef(props, 'chatRoomId'),
            chatHistories: [],
            load: {
                offset: 0,
                limit: 15,
            },
            chatBodyScrollHeight: 0,
            newMessage: false,
            bottomFlag: true,
        });
        const ws = new WebSocket(`ws://localhost:8000/api/v1/chats/conversation/${proxy.$store.getters['user/getProfileId']}/${state.roomId}`);
        const onClickProfile = function(userProfile) {
            emit('followingInfo', userProfile.id);
        }
        const getDefaultProfileImage = function(userProfile) {
            if (userProfile.image === null) {
                return null;
            }
            return userProfile.image.url;
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
            state.newMessage = false;
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
            state.chatBodyScrollHeight = window.$('.chat-detail-body-list').prop('scrollHeight') - state.chatBodyScrollHeight;
            if (state.bottomFlag === true || state.newMessage === false) {
                window.$('.chat-detail-body-list').scrollTop(state.chatBodyScrollHeight);
            }
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
                    state.chatHistories.push(json.data.history);
                    state.newMessage = true;
                } else if (json.type === 'lookup') {
                    state.chatHistories = [...json.data.histories, ...state.chatHistories];
                } else if (json.type === 'file') {
                    state.chatHistories.push(json.data.history);
                } else if (json.type === 'invite') {

                } else if (json.type === 'update') {

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
                'type': 'lookup',
                'data': {
                    'is_read': true
                }
            };
            ws.send(JSON.stringify(data));
        })
        return {
            state,
            onClickProfile,
            getDefaultProfileImage,
            onScrollChatHistories,
            moveChatBodyPosition,
        }
    }
}
</script>

<template>
    <div class="chat-body-list chat-detail-body-list" v-if="state.chatHistories" @scroll="onScrollChatHistories">
        <div v-for="obj in state.chatHistories" :key="obj.id" class="chat-list">
            <div>
                <div v-if="obj.user_profile.image !== null" class="chat-profile" @click="onClickProfile(obj.user_profile)" :style="{
                    backgroundImage: 'url(' + getDefaultProfileImage(obj.user_profile) + ')',
                    backgroundRepeat: 'no-repeat',
                    backgroundSize: 'cover'
                }"></div>
                <div v-else class="chat-profile-default">
                    <p><ui-icon style="width: 100%; height: 100%; color: #b3e5fc">person</ui-icon></p>
                </div>
            </div>
            <div>
                <p style="margin-bottom: 7px;"><b>{{ obj.user_profile.nickname }}</b></p>
                <p>{{ obj.contents }}</p>
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
</style>