<script>
import { reactive, computed, onMounted, getCurrentInstance } from 'vue';

export default {
    name: 'FollowingListLayer',
    setup (props, { emit }) {
      const { proxy } = getCurrentInstance();
      const socket = new WebSocket(`ws://localhost:8000/api/v1/chats/followings/${proxy.$store.getters['user/getProfileId']}`);
      const state = reactive({
        followings: [],
      });
      const getDefaultProfileImage = function(obj) {
        if (obj.files.length > 0) {
            for (const i in obj.files) {
                const file = obj.files[i];
                if (file.use_type === 'user_profile_image' && file.is_default === true) {
                    return file.url;
                }
            }
            return null;
        }
        return null;
      }
      const onClickProfile = function(profileId) {
        emit('followingDetail', profileId);
      }
      onMounted(() => {
        socket.onopen = function(event) {
            console.log('연결 성공');
        }
        socket.onmessage = function(event) {
            state.followings = JSON.parse(event.data);
        }
        socket.onclose = function(event) {
            console.log('close - ', event);
            proxy.$router.replace('/login');
        }
        socket.onerror = function(event) {
            console.log('error - ', event);
            proxy.$router.replace('/login');
        }
      });
      return {
        state,
        getDefaultProfileImage,
        onClickProfile,
      }
    }
}
</script>

<template>
    <div v-if="state.followings">
        <div v-for="obj in state.followings" :key="obj.id" class="following-list" @click="onClickProfile(obj.id)">
            <div v-if="getDefaultProfileImage(obj) !== null" class="following-profile" :style="{
                backgroundImage: 'url(' + getDefaultProfileImage(obj) + ')',
                backgroundRepeat: 'no-repeat',
                backgroundSize: 'cover'
            }"></div>
            <div v-else class="following-profile-default">
                <p><ui-icon style="width: 100%; height: 100%; color: #b3e5fc">person</ui-icon></p>
            </div>
            <p>{{ obj.nickname }}</p>
        </div>
    </div>
</template>

<style scoped>
.following-list {
    display: flex;
    flex-direction: row;
    justify-content: flex-start;
    align-items: center;
    padding: 15px;
    cursor: pointer;
}

.following-list:hover {
    background-color: #f5f5f5;
}

.following-profile-default {
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

.following-profile {
    width: 40px; 
    height: 40px; 
    margin: 0 10px 0 0; 
    border-radius: 50%; 
}
</style>