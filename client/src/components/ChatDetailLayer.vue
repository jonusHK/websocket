<script>
import { reactive, watch, onMounted, getCurrentInstance, toRef, nextTick } from 'vue';
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
            chatHistories: []
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
        onMounted(() => {
            ws.onopen = function(event) {
                console.log('채팅 웹소켓 연결 성공');
            }
            ws.onmessage = function(event) {
                const data = JSON.parse(event.data);
                if (data.type === 'message') {
                    state.chatHistories.push(data.history);
                } else if (data.type === 'lookup') {
                    
                } else if (data.type === 'file') {
                    state.chatHistories.push(data.history);
                } else if (data.type === 'invite') {

                } else if (data.type === 'update') {

                } else if (data.type === 'terminate') {

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
        return {
            state,
            onClickProfile,
            getDefaultProfileImage,
        }
    }
}
</script>

<template>
    <div class="chat-body-list" v-if="state.chatHistories">
        <div v-for="obj in state.chatHistories" :key="obj.id" class="chat-list">
            <div v-if="obj.user_profile.image !== null" class="chat-profile" @click="onClickProfile(obj.user_profile)" :style="{
                backgroundImage: 'url(' + getDefaultProfileImage(obj.user_profile) + ')',
                backgroundRepeat: 'no-repeat',
                backgroundSize: 'cover'
            }"></div>
            <div v-else class="chat-profile-default">
                <p><ui-icon style="width: 100%; height: 100%; color: #b3e5fc">person</ui-icon></p>
            </div>
            <p>{{ obj.user_profile.nickname }}</p>
        </div>
    </div>
</template>

<style scoped>
.chat-list {
    display: flex;
    flex-direction: row;
    justify-content: flex-start;
    align-items: center;
    padding: 15px;
    cursor: pointer;
}

.chat-list:hover {
    background-color: #f5f5f5;
}

.chat-profile-default {
    width: 40px; 
    height: 40px; 
    margin: 0 10px 0 0;
    border-radius: 50%; 
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