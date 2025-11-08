package com.github.dmitryb21.msocialbot.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Data;

import java.time.LocalDate;


public class DailyDomainDto {

    @JsonProperty("domainname")
    private String domainName;

    @JsonProperty("hotness")
    private int hotness;

    @JsonProperty("price")
    private int price;

    @JsonProperty("x_value")
    private int xValue;

    @JsonProperty("yandex_tic")
    private int yandexTic;

    @JsonProperty("links")
    private int links;

    @JsonProperty("visitors")
    private int visitors;

    @JsonProperty("registrar")
    private String registrar;

    @JsonProperty("old")
    private int old;

    @JsonProperty("delete_date")
    private LocalDate deleteDate;

    @JsonProperty("rkn")
    private boolean rkn;

    @JsonProperty("judicial")
    private boolean judicial;

    @JsonProperty("block")
    private boolean block;



    public String getDomainName() {
        return domainName;
    }

    public void setDomainName(String domainName) {
        this.domainName = domainName;
    }

    public int getHotness() {
        return hotness;
    }

    public void setHotness(int hotness) {
        this.hotness = hotness;
    }

    public int getPrice() {
        return price;
    }

    public void setPrice(int price) {
        this.price = price;
    }

    public int getxValue() {
        return xValue;
    }

    public void setxValue(int xValue) {
        this.xValue = xValue;
    }

    public int getYandexTic() {
        return yandexTic;
    }

    public void setYandexTic(int yandexTic) {
        this.yandexTic = yandexTic;
    }

    public int getLinks() {
        return links;
    }

    public void setLinks(int links) {
        this.links = links;
    }

    public int getVisitors() {
        return visitors;
    }

    public void setVisitors(int visitors) {
        this.visitors = visitors;
    }

    public String getRegistrar() {
        return registrar;
    }

    public void setRegistrar(String registrar) {
        this.registrar = registrar;
    }

    public int getOld() {
        return old;
    }

    public void setOld(int old) {
        this.old = old;
    }

    public LocalDate getDeleteDate() {
        return deleteDate;
    }

    public void setDeleteDate(LocalDate deleteDate) {
        this.deleteDate = deleteDate;
    }

    public boolean isRkn() {
        return rkn;
    }

    public void setRkn(boolean rkn) {
        this.rkn = rkn;
    }

    public boolean isJudicial() {
        return judicial;
    }

    public void setJudicial(boolean judicial) {
        this.judicial = judicial;
    }

    public boolean isBlock() {
        return block;
    }

    public void setBlock(boolean block) {
        this.block = block;
    }
}
