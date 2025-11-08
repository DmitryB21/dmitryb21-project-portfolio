package ru.dblukherov.todo.backend.search;

import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@NoArgsConstructor
@Getter
@Setter
@AllArgsConstructor

//возможные значения по которым можно искать категории
public class CategorySearchValues {

    private String title;  // такое же значение должно быть у объекта на frontend
    private String email;  // для фильтрации значений конкретного пользователя
}
