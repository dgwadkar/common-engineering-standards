/*
 * ArchUnit fixture — Logic Hole #6 (constructor-injection mandate).
 *
 * Source rule: source/java/spring-boot/di/constructor-injection-mandate.md
 * Phase 6 — docs/02-implementation-plan.md §9 task 5.
 *
 * Distribution: ships at
 * `src/test/java/com/_org/standards/archunit/ConstructorInjectionTest.java`
 * via Phase 8's consumer-sync CLI.
 *
 * Expected behavior in a Spring Boot 3 consumer project containing one
 * deliberate violation per rule:
 *
 *   - noFieldsAnnotatedWithAutowired
 *       FAILS with: "Field <Class>.<f> is annotated @Autowired; use
 *       constructor injection with `private final` fields instead
 *       (constructor-injection-mandate.md §2.1).".
 *
 *   - noSetterAutowired
 *       FAILS with: "Method <Class>.<m> is a setter annotated @Autowired;
 *       use constructor injection with `private final` fields instead
 *       (constructor-injection-mandate.md §2.1).".
 *
 *   - springBeanFieldsMustBeFinal
 *       FAILS with: "Field <Class>.<f> in a Spring-managed bean is not
 *       declared `final`; constructor injection requires final fields so
 *       reflection or a misbehaving subclass cannot null the dependency
 *       (constructor-injection-mandate.md §2.1).".
 */
package com._org.standards.archunit;

import com.tngtech.archunit.core.domain.JavaClass;
import com.tngtech.archunit.core.domain.JavaField;
import com.tngtech.archunit.core.domain.JavaMethod;
import com.tngtech.archunit.core.domain.JavaModifier;
import com.tngtech.archunit.core.importer.ImportOption;
import com.tngtech.archunit.junit.AnalyzeClasses;
import com.tngtech.archunit.junit.ArchTest;
import com.tngtech.archunit.lang.ArchCondition;
import com.tngtech.archunit.lang.ArchRule;
import com.tngtech.archunit.lang.ConditionEvents;
import com.tngtech.archunit.lang.SimpleConditionEvent;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.annotation.Configuration;
import org.springframework.stereotype.Component;
import org.springframework.stereotype.Controller;
import org.springframework.stereotype.Repository;
import org.springframework.stereotype.Service;
import org.springframework.web.bind.annotation.RestController;

import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.fields;
import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.methods;

@AnalyzeClasses(
        packages = "com._org",
        importOptions = {ImportOption.DoNotIncludeTests.class}
)
public class ConstructorInjectionTest {

    /**
     * Rule 2.1 of constructor-injection-mandate.md (defect class A).
     *
     * No field on any Spring-managed class may carry @Autowired.
     */
    @ArchTest
    public static final ArchRule noFieldsAnnotatedWithAutowired =
            fields()
                    .that().areDeclaredInClassesThat().areAnnotatedWith(Component.class)
                    .or().areDeclaredInClassesThat().areAnnotatedWith(Service.class)
                    .or().areDeclaredInClassesThat().areAnnotatedWith(Repository.class)
                    .or().areDeclaredInClassesThat().areAnnotatedWith(Controller.class)
                    .or().areDeclaredInClassesThat().areAnnotatedWith(RestController.class)
                    .or().areDeclaredInClassesThat().areAnnotatedWith(Configuration.class)
                    .should().notBeAnnotatedWith(Autowired.class)
                    .as("Spring-managed beans must not use @Autowired field injection")
                    .because("constructor-injection-mandate.md §2.1: field injection breaks testability and immutability");

    /**
     * Rule 2.1 of constructor-injection-mandate.md (defect class B).
     *
     * No setter (`set*` method, single parameter, void return) on a
     * Spring-managed class may carry @Autowired.
     */
    @ArchTest
    public static final ArchRule noSetterAutowired =
            methods()
                    .that().areAnnotatedWith(Autowired.class)
                    .should(notBeASetter())
                    .as("Spring-managed beans must not use @Autowired setter injection")
                    .because("constructor-injection-mandate.md §2.1: setter injection breaks immutability and obscures the contract");

    /**
     * Rule 2.1 of constructor-injection-mandate.md (defect class C).
     *
     * Every instance field of a Spring-managed bean must be declared
     * `final`. Static fields, logger fields, and constants are excluded.
     */
    @ArchTest
    public static final ArchRule springBeanFieldsMustBeFinal =
            fields()
                    .that().areDeclaredInClassesThat().areAnnotatedWith(Service.class)
                    .or().areDeclaredInClassesThat().areAnnotatedWith(Component.class)
                    .or().areDeclaredInClassesThat().areAnnotatedWith(Repository.class)
                    .or().areDeclaredInClassesThat().areAnnotatedWith(Controller.class)
                    .or().areDeclaredInClassesThat().areAnnotatedWith(RestController.class)
                    .should(beFinalUnlessStaticOrLoggerField())
                    .as("Instance fields on Spring-managed beans must be `final`")
                    .because("constructor-injection-mandate.md §2.1: final dependencies cannot be null'd post-construction");

    // --- Custom conditions -------------------------------------------------

    private static ArchCondition<JavaMethod> notBeASetter() {
        return new ArchCondition<>("not be a setter (set*, single argument, void return)") {
            @Override
            public void check(JavaMethod method, ConditionEvents events) {
                boolean looksLikeSetter =
                        method.getName().startsWith("set")
                                && method.getRawParameterTypes().size() == 1
                                && method.getRawReturnType().getFullName().equals("void");
                if (looksLikeSetter) {
                    String message = String.format(
                            "Method %s.%s is a setter annotated @Autowired; use constructor injection "
                                    + "with `private final` fields instead "
                                    + "(constructor-injection-mandate.md §2.1).",
                            method.getOwner().getFullName(),
                            method.getName());
                    events.add(SimpleConditionEvent.violated(method, message));
                }
            }
        };
    }

    private static ArchCondition<JavaField> beFinalUnlessStaticOrLoggerField() {
        return new ArchCondition<>("be `final` (or static, or a logger constant)") {
            @Override
            public void check(JavaField field, ConditionEvents events) {
                if (field.getModifiers().contains(JavaModifier.STATIC)) {
                    return;
                }
                if (field.getModifiers().contains(JavaModifier.FINAL)) {
                    return;
                }
                String fieldType = field.getRawType().getFullName();
                if (fieldType.equals("org.slf4j.Logger")
                        || fieldType.equals("org.apache.logging.log4j.Logger")) {
                    return; // logger declared as instance field — common pattern, allowed
                }
                String message = String.format(
                        "Field %s.%s in a Spring-managed bean is not declared `final`; "
                                + "constructor injection requires final fields so reflection or a "
                                + "misbehaving subclass cannot null the dependency "
                                + "(constructor-injection-mandate.md §2.1).",
                        field.getOwner().getFullName(),
                        field.getName());
                events.add(SimpleConditionEvent.violated(field, message));
            }
        };
    }
}
