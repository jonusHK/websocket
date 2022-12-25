<script>
import { reactive, watch, onMounted, getCurrentInstance, toRef, nextTick } from 'vue';
import constants from '../constants';

const { VITE_SERVER_HOST } = import.meta.env;


export default {
    name: 'FollowingListLayer',
    props: {
      userProfileId: Number
    },
    setup (props, { emit }) {
      const { proxy } = getCurrentInstance();
      const state = reactive({
        profileId: toRef(props, 'userProfileId'),
        profileNickname: '',
        profileStatusMessage: '',
        profileImages: [],
        profileDefaultImage: '',
        profileIsDefault: false,
        profileIsActive: true,
      });
      const getUserProfileDetail = async function(profileId) {
        proxy.$axios.get(VITE_SERVER_HOST + `/users/profile/${profileId}`)
        .then((res) => {
            if (res.status === 200) {
                state.profileNickname = res.data.data.nickname;
                state.profileStatusMessage = res.data.data.status_message;
                state.profileImages = res.data.data.images;
                state.profileDefaultImage = getDefaultProfileImage(state.profileImages);
                state.profileIsDefault = res.data.data.is_default;
                state.profileIsActive = res.data.data.is_active;
            }
        })
        .catch((err) => {
            proxy.$alert({
                state: 'error',
                stateOutlined: true,
                message: err.response.data.message,
            })
        })
        await nextTick();
      }
      const getDefaultProfileImage = function(images) {
        for (const idx in images) {
            const image = images[idx];
            if (constants.profileImageType[image.type] === 'profile' && image.is_default === true) {
                return image.url;
            }
        }
        return null;
      }
      watch(
        () => props.userProfileId,
        (cur, prev) => {
            getUserProfileDetail(cur)
        },
      )
      onMounted(() => {
        getUserProfileDetail(state.profileId);
      })
      return {
        state,
        getUserProfileDetail,
        getDefaultProfileImage,
      }
    }
}
</script>

<template>
    <div class="chat-body-detail-summary">
        <div>
            {{  state.profileNickname }}
        </div>
    </div>
    <div class="chat-body-detail-view">
        <div class="profile-image-layout">
            <div 
                class="profile-image"
                v-if="state.profileDefaultImage !== null"
                :style="{
                    backgroundImage: 'url(' + state.profileDefaultImage + ')',
                    backgroundRepeat: 'no-repeat',
                    backgroundSize: 'cover'
                }"
            ></div>
            <div v-else class="profile-image-default">
                <div><ui-icon style="width: 100%; height: 100%; color: #b3e5fc" :size="48">person</ui-icon></div>
            </div>
        </div>
    </div>
</template>

<style scoped>
.profile-image-layout {
    display: flex;
    flex-direction: row;
    justify-content: center;
    align-items: center;
}

.profile-image {
    width: 250px;
    height: 250px;
    border-radius: 5%;
}

.profile-image-default {
    width: 250px;
    height: 250px;
    border-radius: 5%;
    margin: 0;
    background-color: #81d4fa;
    display: flex;
    flex-direction: row;
    justify-content: center;
    align-items: center;
}
</style>