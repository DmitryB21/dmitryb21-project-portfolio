package ru.dblukherov.todo.backend.aop;


import lombok.extern.java.Log;
import org.aspectj.lang.ProceedingJoinPoint;
import org.aspectj.lang.annotation.Around;
import org.aspectj.lang.annotation.Aspect;
import org.aspectj.lang.reflect.MethodSignature;
import org.springframework.stereotype.Component;
import org.springframework.util.StopWatch;

@Aspect
@Component
@Log
public class LoggingAspect {

    //аспект будет выполнятся для всех методов из пакета контроллеров
    @Around("execution(* ru.dblukherov.todo.backend.controller..*(..)))")
    public Object profileControllerMethods(ProceedingJoinPoint proceedingJoinPoint) throws Throwable
    {
        MethodSignature methodSignature = (MethodSignature) proceedingJoinPoint.getSignature();

        //сччитываем какой класс и метод выполняется
        String className = methodSignature.getDeclaringType().getSimpleName();
        String methodName = methodSignature.getName();

        log.info("----------- Execution  " + className + "." + methodName + "    -------------");

        StopWatch stopWatch = new StopWatch();

        stopWatch.start(); //запуск

        //выполняем сам метод
        Object result = proceedingJoinPoint.proceed();

        stopWatch.stop();

        log.info("----------- Execution time of " + className + "." + methodName + " :: " + stopWatch.getTotalTimeMillis() + "ms");


        return result;

    }

}
