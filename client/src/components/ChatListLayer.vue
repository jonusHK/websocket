<script>
import { reactive, watch, onMounted, getCurrentInstance, toRef, nextTick } from 'vue';
import constants from '../constants';

const { VITE_SERVER_HOST } = import.meta.env;


export default {
    name: 'ChatListLayer',
    props: {},
    setup (props, { emit }) {
        const { proxy } = getCurrentInstance();
        const ws = new WebSocket(`ws://localhost:8000/api/v1/chats/rooms/${proxy.$store.getters['user/getProfileId']}`);
        const state = reactive({
            chatRooms: [],
        });
        const getChatRoomImage = function(obj) {
            if (obj.user_profile_files.length > 0) {
                let files = [];
                for (const i in obj.user_profile_files) {
                    const file = obj.user_profile_files[i];
                    if (file.use_type === 'user_profile_image' && file.is_default === true) {
                        files.push(file.url);
                    }
                }
                if (files.length !== 0) {
                    // TODO 여러 배경 이미지로 렌더링하도록 변경
                    return files[0];
                }
                return null;
            }
            return null;
        }
        const onClickChatRoom = function(roomId) {
            emit('chatDetail', roomId);
        }
        onMounted(() => {
            ws.onopen = function(event) {
                console.log('채팅방 목록 웹소켓 연결 성공');
            }
            ws.onmessage = function(event) {
                state.chatRooms = JSON.parse(event.data);
            }
            ws.onclose = function(event) {
                console.log('close - ', event);
                proxy.$router.replace('/login');
            }
            ws.onerror = function(event) {
                console.log('error - ', event);
                proxy.$router.replace('/login');
            }
        });
        return {
        state,
        getChatRoomImage,
        onClickChatRoom,
      }
    }
}
</script>

<template>
    <div class="chat-body-list" v-if="state.chatRooms">
        <div v-for="obj in state.chatRooms" :key="obj.id" class="chat-room-list" @click="onClickChatRoom(obj.id)">
            <div v-if="getChatRoomImage(obj) !== null" class="chat-room-image" :style="{
                backgroundImage: 'url(' + getChatRoomImage(obj) + ')',
                backgroundRepeat: 'no-repeat',
                backgroundSize: 'cover'
            }"></div>
            <div v-else class="chat-room-image-default">
                <p><ui-icon style="width: 100%; height: 100%; color: #b3e5fc">person</ui-icon></p>
            </div>
            <p>{{ obj.name }}</p>
        </div>
    </div>
</template>

<style scoped>
.chat-room-list {
    display: flex;
    flex-direction: row;
    justify-content: flex-start;
    align-items: center;
    padding: 15px;
    cursor: pointer;
}

.chat-room-list:hover {
    background-color: #f5f5f5;
}

.chat-room-image-default {
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

.chat-room-image {
    width: 40px; 
    height: 40px; 
    margin: 0 10px 0 0; 
    border-radius: 50%; 
}
</style>
