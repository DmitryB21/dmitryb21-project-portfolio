package com.skypro.resale.exception;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ControllerAdvice;
import org.springframework.web.bind.annotation.ExceptionHandler;


@ControllerAdvice
public class NotFoundControllerAdvice {

    @ExceptionHandler(UsernameNotFoundException.class)
    public ResponseEntity<?> notFoundUsername(){
        return ResponseEntity.status(HttpStatus.NOT_FOUND).build();
    }

    @ExceptionHandler(AdsNotFoundException.class)
    public ResponseEntity<?> notFoundAds(){
        return ResponseEntity.status(HttpStatus.NOT_FOUND).build();
    }

    @ExceptionHandler(ImageNotFoundException.class)
    public ResponseEntity<?> notFoundImage(){
        return ResponseEntity.status(HttpStatus.NOT_FOUND).build();
    }

    @ExceptionHandler(CommentNotFoundException.class)
    public ResponseEntity<?> notFoundComment() {
        return ResponseEntity.status(HttpStatus.NOT_FOUND).build();
    }

}
