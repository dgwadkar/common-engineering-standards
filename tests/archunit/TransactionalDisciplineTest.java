/*
 * ArchUnit fixture — Logic Hole #4 (transactional discipline).
 *
 * Source rules:
 *   - source/java/spring-boot/service/transactional-boundaries.md
 *   - source/java/spring-boot/service/transactional-readonly.md
 *   - source/java/spring-boot/service/self-invocation-trap.md
 *
 * Phase 6 — docs/02-implementation-plan.md §9 task 5.
 *
 * Distribution: ships at
 * `src/test/java/com/_org/standards/archunit/TransactionalDisciplineTest.java`
 * via Phase 8's consumer-sync CLI.
 *
 * Expected behavior in a Spring Boot 3 consumer project containing one
 * deliberate violation per rule:
 *
 *   - transactionalMethodsMustNotInvokeBlockingHttpClients
 *       FAILS with: "Method <Class>.<m>(...) annotated @Transactional
 *       calls a blocking HTTP client (RestTemplate / RestClient /
 *       WebClient.block / FeignClient) — extract the DB-only critical
 *       section into TransactionTemplate.execute(...) and perform the I/O
 *       outside the transaction (transactional-boundaries.md §2.1).".
 *
 *   - transactionalAnnotationsLiveOnPublicMethodsOnly
 *       FAILS with: "Method <Class>.<m> is annotated @Transactional but
 *       is not public; Spring's proxy-based AOP cannot intercept non-public
 *       methods (self-invocation-trap.md §2.1).".
 *
 *   - servicesShouldDeclareReadOnlyDefaultAtClassLevel
 *       FAILS with: "Class <Class> annotated @Service declares no
 *       class-level @Transactional(readOnly = true) default; readOnly is
 *       the safer default and must be set at the class level
 *       (transactional-readonly.md §2.1).".
 */
package com._org.standards.archunit;

import com.tngtech.archunit.core.domain.JavaAnnotation;
import com.tngtech.archunit.core.domain.JavaClass;
import com.tngtech.archunit.core.domain.JavaMethod;
import com.tngtech.archunit.core.domain.JavaModifier;
import com.tngtech.archunit.core.importer.ImportOption;
import com.tngtech.archunit.junit.AnalyzeClasses;
import com.tngtech.archunit.junit.ArchTest;
import com.tngtech.archunit.lang.ArchCondition;
import com.tngtech.archunit.lang.ArchRule;
import com.tngtech.archunit.lang.ConditionEvents;
import com.tngtech.archunit.lang.SimpleConditionEvent;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.classes;
import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.methods;

@AnalyzeClasses(
        packages = "com._org",
        importOptions = {ImportOption.DoNotIncludeTests.class}
)
public class TransactionalDisciplineTest {

    /**
     * Rule 2.1 of transactional-boundaries.md.
     *
     * No call to a blocking HTTP / gRPC / message-broker client is allowed
     * inside an @Transactional method body. The connection-pool starvation
     * pathology described in §1 of the rule.
     */
    @ArchTest
    public static final ArchRule transactionalMethodsMustNotInvokeBlockingHttpClients =
            methods()
                    .that().areAnnotatedWith(Transactional.class)
                    .or().areDeclaredInClassesThat().areAnnotatedWith(Transactional.class)
                    .should(notInvokeBlockingClients())
                    .as("@Transactional methods must not call blocking HTTP/gRPC/broker clients")
                    .because("transactional-boundaries.md §2.1: a held DB connection during external I/O exhausts the pool");

    /**
     * Rule 2.1 of self-invocation-trap.md.
     *
     * Spring's proxy-based AOP only intercepts public methods invoked
     * through a managed bean reference. @Transactional on a private,
     * package-private, or protected method is silently ignored.
     */
    @ArchTest
    public static final ArchRule transactionalAnnotationsLiveOnPublicMethodsOnly =
            methods()
                    .that().areAnnotatedWith(Transactional.class)
                    .should().bePublic()
                    .as("@Transactional methods must be public")
                    .because("self-invocation-trap.md §2.1: proxy-based AOP cannot intercept non-public methods");

    /**
     * Rule 2.1 of transactional-readonly.md.
     *
     * Services that touch the data layer should declare
     * @Transactional(readOnly = true) at the class level so every method's
     * default is read-only; write methods opt back in with method-level
     * @Transactional (without readOnly).
     */
    @ArchTest
    public static final ArchRule servicesShouldDeclareReadOnlyDefaultAtClassLevel =
            classes()
                    .that().areAnnotatedWith(Service.class)
                    .should(declareClassLevelReadOnlyTransactionalDefault())
                    .as("@Service classes must declare @Transactional(readOnly = true) at the class level")
                    .because("transactional-readonly.md §2.1: readOnly is the safer default and must be class-level");

    // --- Custom conditions -------------------------------------------------

    /**
     * Bytecode pattern set covering the most common blocking client APIs in
     * Spring Boot 3 stacks. The list is intentionally conservative — false
     * negatives (a custom blocking client wrapper) are caught at code review;
     * false positives would be operationally costly.
     */
    private static final java.util.List<String> BLOCKING_CLIENT_FQNS = java.util.List.of(
            "org.springframework.web.client.RestTemplate",
            "org.springframework.web.client.RestClient",
            "org.springframework.web.reactive.function.client.WebClient", // .block()
            "feign.Client",
            "org.apache.kafka.clients.producer.KafkaProducer",            // .send().get()
            "org.springframework.kafka.core.KafkaTemplate",
            "org.springframework.amqp.rabbit.core.RabbitTemplate"
    );

    private static ArchCondition<JavaMethod> notInvokeBlockingClients() {
        return new ArchCondition<>("not invoke a blocking HTTP/gRPC/broker client") {
            @Override
            public void check(JavaMethod method, ConditionEvents events) {
                method.getCallsFromSelf().forEach(call -> {
                    String calleeOwner = call.getTargetOwner().getFullName();
                    for (String blockingFqn : BLOCKING_CLIENT_FQNS) {
                        if (calleeOwner.equals(blockingFqn)) {
                            String message = String.format(
                                    "Method %s.%s(...) annotated @Transactional calls a blocking HTTP client "
                                            + "(%s.%s) — extract the DB-only critical section into "
                                            + "TransactionTemplate.execute(...) and perform the I/O outside "
                                            + "the transaction (transactional-boundaries.md §2.1).",
                                    method.getOwner().getFullName(),
                                    method.getName(),
                                    calleeOwner,
                                    call.getName());
                            events.add(SimpleConditionEvent.violated(method, message));
                            return;
                        }
                    }
                });
            }
        };
    }

    private static ArchCondition<JavaClass> declareClassLevelReadOnlyTransactionalDefault() {
        return new ArchCondition<>("declare class-level @Transactional(readOnly = true)") {
            @Override
            public void check(JavaClass clazz, ConditionEvents events) {
                java.util.Optional<? extends JavaAnnotation<?>> txAnnotation =
                        clazz.tryGetAnnotationOfType(Transactional.class.getName());
                if (txAnnotation.isEmpty()) {
                    String message = String.format(
                            "Class %s annotated @Service declares no class-level @Transactional(readOnly = true) "
                                    + "default; readOnly is the safer default and must be set at the class level "
                                    + "(transactional-readonly.md §2.1).",
                            clazz.getFullName());
                    events.add(SimpleConditionEvent.violated(clazz, message));
                    return;
                }
                Object readOnlyValue = txAnnotation.get().getProperties().get("readOnly");
                boolean readOnlyTrue = readOnlyValue instanceof Boolean && (Boolean) readOnlyValue;
                if (!readOnlyTrue) {
                    String message = String.format(
                            "Class %s annotated @Service has class-level @Transactional but readOnly is "
                                    + "false (or unset); set readOnly = true so write methods opt back in "
                                    + "(transactional-readonly.md §2.1).",
                            clazz.getFullName());
                    events.add(SimpleConditionEvent.violated(clazz, message));
                }
            }
        };
    }
}
