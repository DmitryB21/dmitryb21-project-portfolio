package com.skypro.resale.model;

import lombok.Data;

import javax.persistence.*;
import javax.validation.constraints.NotNull;
@Entity
@Data
@Table
public class Comment {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Integer id;
    @NotNull
    private Long createdAt;
    @NotNull
    private String text;
    @ManyToOne(fetch = FetchType.LAZY)
    private Ad ads;
    @ManyToOne(fetch = FetchType.LAZY)
    private User author;

}