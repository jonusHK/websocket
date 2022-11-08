<template>
    <div>
      <div>
        <user-list-layer/>
        <room-title-layer/>
        <chat-list-layer/>
        <chat-input-layer/>
      </div>
      <div>
        <user-profile-layer/>
      </div>
    </div>
</template>

<script>
import RoomTitleLayer from './RoomTitleLayer.vue';
import ChatListLayer from './ChatListLayer.vue';
import ChatInputLayer from './ChatInputLayer.vue';
import UserProfileLayer from './UserProfileLayer.vue';
import UserListLayer from './UserListLayer.vue';

export default {
  name: 'MainLayer.vue',
  components: {
    RoomTitleLayer,
    ChatListLayer,
    ChatInputLayer,
    UserProfileLayer,
    UserListLayer,
  }
}
</script>
