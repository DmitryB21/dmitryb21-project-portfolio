package com.skypro.resale.mapper;

import com.skypro.resale.dto.UserDto;
import com.skypro.resale.model.Avatar;
import com.skypro.resale.model.User;
import org.mapstruct.Mapper;
import org.mapstruct.Mapping;
import org.mapstruct.Named;
import org.mapstruct.factory.Mappers;



@Mapper(componentModel = "spring")
public interface UserMapper {

    String USER_AVATAR = "/users/avatar/";
    UserMapper INSTANCE = Mappers.getMapper(UserMapper.class);

    @Mapping(target = "image", source = "avatar", qualifiedByName = "avatarMapping")
    UserDto toDto(User user);

    @Named("avatarMapping")
    default String avatarMapping(Avatar avatar) {
        if (avatar == null) {
            return null;
        }
        return USER_AVATAR + avatar.getId();
    }

}
