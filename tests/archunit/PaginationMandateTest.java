/*
 * ArchUnit fixture — Logic Hole #5 (pagination mandate).
 *
 * Source rules:
 *   - source/java/spring-boot/repository/findall-pagination-mandate.md
 *   - source/java/spring-boot/controller/pageable-defaults.md
 *
 * Phase 6 — docs/02-implementation-plan.md §9 task 5.
 *
 * Distribution: ships at
 * `src/test/java/com/_org/standards/archunit/PaginationMandateTest.java`
 * via Phase 8's consumer-sync CLI.
 *
 * Expected behavior in a Spring Boot 3 consumer project containing one
 * deliberate violation per rule:
 *
 *   - repositoryListReturnsMustAcceptPageable
 *       FAILS with: "Method <Repository>.<m>(...) returns
 *       List/Iterable/Stream/Set/Collection<T> without a Pageable parameter
 *       — re-type the return to Page<T>/Slice<T> and accept Pageable, OR
 *       annotate with @SuppressWarnings(\"PaginationMandate\") and document
 *       the bounded result set (findall-pagination-mandate.md §2.1).".
 *
 *   - controllerListEndpointsMustAcceptPageableOrPageRequestParam
 *       FAILS with: "Method <Controller>.<m>(...) returns a list-typed
 *       response without accepting a Pageable parameter; HTTP list endpoints
 *       must paginate (pageable-defaults.md §2.1).".
 */
package com._org.standards.archunit;

import com.tngtech.archunit.core.domain.JavaClass;
import com.tngtech.archunit.core.domain.JavaMethod;
import com.tngtech.archunit.core.importer.ImportOption;
import com.tngtech.archunit.junit.AnalyzeClasses;
import com.tngtech.archunit.junit.ArchTest;
import com.tngtech.archunit.lang.ArchCondition;
import com.tngtech.archunit.lang.ArchRule;
import com.tngtech.archunit.lang.ConditionEvents;
import com.tngtech.archunit.lang.SimpleConditionEvent;

import org.springframework.data.domain.Pageable;
import org.springframework.data.repository.Repository;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.methods;

@AnalyzeClasses(
        packages = "com._org",
        importOptions = {ImportOption.DoNotIncludeTests.class}
)
public class PaginationMandateTest {

    /**
     * Rule 2.1 of findall-pagination-mandate.md.
     *
     * Any repository method returning a multi-row collection type (List,
     * Iterable, Stream, Set, Collection) must accept a Pageable AND return
     * Page<T>/Slice<T>. The lone exception is a method tagged
     * @SuppressWarnings("PaginationMandate") for a bounded lookup table.
     */
    @ArchTest
    public static final ArchRule repositoryListReturnsMustAcceptPageable =
            methods()
                    .that().areDeclaredInClassesThat().areAssignableTo(Repository.class)
                    .or().areDeclaredInClassesThat().haveNameMatching(".*Repository")
                    .and().areNotPrivate()
                    .should(acceptPageableWhenReturningCollections())
                    .as("Repository methods returning collections must accept Pageable and return Page/Slice")
                    .because("findall-pagination-mandate.md §2.1: unbounded list queries are latent OOMs and serialization-buffer overflows");

    /**
     * Rule 2.1 of pageable-defaults.md.
     *
     * Any @RestController @GetMapping method whose return type is a list /
     * iterable / collection of domain objects must accept a Pageable
     * parameter so Spring Web's PageableHandlerMethodArgumentResolver
     * applies bounded defaults.
     */
    @ArchTest
    public static final ArchRule controllerListEndpointsMustAcceptPageableOrPageRequestParam =
            methods()
                    .that().areDeclaredInClassesThat().areAnnotatedWith(RestController.class)
                    .and().areAnnotatedWith(GetMapping.class)
                    .or().areDeclaredInClassesThat().areAnnotatedWith(RestController.class)
                    .and().areAnnotatedWith(RequestMapping.class)
                    .should(acceptPageableWhenReturningCollections())
                    .as("Controller list endpoints must accept Pageable")
                    .because("pageable-defaults.md §2.1: list endpoints must paginate at the HTTP boundary");

    // --- Custom conditions -------------------------------------------------

    private static final java.util.Set<String> COLLECTION_RETURN_TYPES = java.util.Set.of(
            "java.util.List",
            "java.util.Collection",
            "java.lang.Iterable",
            "java.util.stream.Stream",
            "java.util.Set"
    );

    private static ArchCondition<JavaMethod> acceptPageableWhenReturningCollections() {
        return new ArchCondition<>("accept Pageable when returning a list-typed result") {
            @Override
            public void check(JavaMethod method, ConditionEvents events) {
                JavaClass returnType = method.getRawReturnType();
                String returnFqn = returnType.getFullName();
                if (!COLLECTION_RETURN_TYPES.contains(returnFqn)) {
                    return; // not a list-typed return — rule does not apply
                }
                if (method.tryGetAnnotationOfType("java.lang.SuppressWarnings").isPresent()) {
                    Object value = method.tryGetAnnotationOfType("java.lang.SuppressWarnings")
                            .get()
                            .getProperties()
                            .get("value");
                    if (value instanceof String[] array) {
                        for (String token : array) {
                            if ("PaginationMandate".equals(token)) {
                                return; // audited-bounded exception
                            }
                        }
                    } else if (value instanceof String token && "PaginationMandate".equals(token)) {
                        return;
                    }
                }
                boolean hasPageable = method.getRawParameterTypes().stream()
                        .anyMatch(p -> p.getFullName().equals(Pageable.class.getName()));
                if (!hasPageable) {
                    String message = String.format(
                            "Method %s.%s(...) returns %s<T> without a Pageable parameter — "
                                    + "re-type the return to Page<T>/Slice<T> and accept Pageable, OR "
                                    + "annotate with @SuppressWarnings(\"PaginationMandate\") and document "
                                    + "the bounded result set (findall-pagination-mandate.md §2.1).",
                            method.getOwner().getFullName(),
                            method.getName(),
                            returnFqn);
                    events.add(SimpleConditionEvent.violated(method, message));
                }
            }
        };
    }
}
