package ru.dblukherov.todo.backend.repo;


import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;
import ru.dblukherov.todo.backend.entity.Category;

import java.util.List;

@Repository
public interface CategoryRepository extends JpaRepository<Category,Long> {
    List<Category> findByUserEmailOrderByTitleAsc(String email);

    @Query(value = "SELECT c FROM Category c where" +
    "(:title is null or :title=''" +    //3.если title пустой, выберутся все записи конкретного email, без фильтрации
    "or lower(c.title) like lower(concat('%', :title, '%'))) " +   // 2.если title не пустой, запрос,по вхождению текста типа like (приводим к нижнему регистру)
    "and c.user.email=:email" +    //1.фильтрация для конкретного пользователя(email)
    " order by c.title asc")    //4.сортировка по title(по алфавиту)
    List<Category>findByTitle(@Param("title")String title, @Param("email") String email);



}
