package ru.dblukherov.todo.backend.service;


import org.springframework.stereotype.Service;
import ru.dblukherov.todo.backend.entity.Category;
import ru.dblukherov.todo.backend.repo.CategoryRepository;


import javax.transaction.Transactional;
import java.util.List;

@Service
@Transactional
public class CategoryService {

    private final CategoryRepository repository;

    public CategoryService(CategoryRepository repository) {
        this.repository = repository;
    }
    public List<Category> findAll(String email){
        return repository.findByUserEmailOrderByTitleAsc(email);
    }

    public Category add(Category category){
        return repository.save(category);
    }
    public Category update(Category category){
        return repository.save(category);
    }

    public void deleteById(Long id){
        repository.deleteById(id);
    }

    public List<Category>findByTitle(String text, String email){
        return repository.findByTitle(text, email);
    }

    public Category findById(Long id){
        return repository.findById(id).get();
    }
}
