/*
 * ArchUnit fixture — Logic Hole #3 (controller validation boundaries).
 *
 * Source rule: source/java/spring-boot/controller/validation-boundaries.md
 * Companion rules: dto-record-mandate.md, pageable-defaults.md
 * Phase 6 — docs/02-implementation-plan.md §9 task 5.
 *
 * Distribution: ships into consumer projects via Phase 8's `@org/standards-sync`
 * CLI at `src/test/java/com/_org/standards/archunit/ControllerValidationTest.java`.
 * The file is hand-authored static text in this repo (Phase 6 deliverable);
 * consumer-side execution is what fails when a violation is committed.
 *
 * Expected behavior in a Spring Boot 3 consumer project containing one
 * deliberate violation per rule:
 *
 *   - controllerRequestBodiesMustBeAnnotatedWithValid
 *       FAILS with: "Method <Controller>.<m>(...) declares an @RequestBody
 *       parameter that is not annotated with @Valid".
 *
 *   - controllersWithParameterConstraintsMustBeAnnotatedWithValidated
 *       FAILS with: "Class <Controller> declares Jakarta Validation
 *       constraints on @PathVariable or @RequestParam without a class-level
 *       @Validated annotation".
 *
 *   - controllersMustResideInControllerOrWebPackage
 *       FAILS with: "Class <Controller> annotated @RestController is not
 *       in a package matching ..controller.. or ..web..".
 *
 * Verification procedure (manual; requires JDK 17 + Maven):
 *
 *   $ cd <consumer-project-with-spring-boot-3>
 *   $ cp <this-file>  src/test/java/com/_org/standards/archunit/
 *   $ mvn -Dtest=ControllerValidationTest test          # all rules pass on clean code
 *   $ # introduce a deliberate violation per the docstrings above
 *   $ mvn -Dtest=ControllerValidationTest test          # rules fail with the messages above
 */
package com._org.standards.archunit;

import com.tngtech.archunit.core.domain.JavaClasses;
import com.tngtech.archunit.core.importer.ClassFileImporter;
import com.tngtech.archunit.core.importer.ImportOption;
import com.tngtech.archunit.junit.AnalyzeClasses;
import com.tngtech.archunit.junit.ArchTest;
import com.tngtech.archunit.lang.ArchCondition;
import com.tngtech.archunit.lang.ArchRule;
import com.tngtech.archunit.lang.ConditionEvents;
import com.tngtech.archunit.lang.SimpleConditionEvent;
import com.tngtech.archunit.lang.syntax.ArchRuleDefinition;

import jakarta.validation.Valid;
import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Positive;
import jakarta.validation.constraints.Size;

import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.ModelAttribute;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RequestPart;
import org.springframework.web.bind.annotation.RestController;

import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.classes;
import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.methods;

@AnalyzeClasses(
        packages = "com._org",
        importOptions = {ImportOption.DoNotIncludeTests.class}
)
public class ControllerValidationTest {

    /**
     * Rule 2.1 of validation-boundaries.md.
     *
     * Every controller method parameter annotated with one of @RequestBody,
     * @RequestPart, or @ModelAttribute must also carry @Valid (or @Validated).
     *
     * Violation message: "Method &lt;Controller&gt;.&lt;m&gt;(...) declares an
     * @RequestBody parameter that is not annotated with @Valid".
     */
    @ArchTest
    public static final ArchRule controllerRequestBodiesMustBeAnnotatedWithValid =
            methods()
                    .that().areDeclaredInClassesThat().areAnnotatedWith(RestController.class)
                    .should(haveValidActivatorOnEveryRequestBoundParameter())
                    .as("Controller methods must annotate @RequestBody/@RequestPart/@ModelAttribute parameters with @Valid")
                    .because("validation-boundaries.md Rule 2.1: constraints on the DTO are inert without @Valid");

    /**
     * Rule 2.2 of validation-boundaries.md.
     *
     * Controllers that put Jakarta Validation constraints directly on
     * @PathVariable / @RequestParam parameters must annotate the class with
     * @Validated to register Spring's method-level validation interceptor.
     *
     * Violation message: "Class &lt;Controller&gt; declares Jakarta
     * Validation constraints on @PathVariable or @RequestParam without a
     * class-level @Validated annotation".
     */
    @ArchTest
    public static final ArchRule controllersWithParameterConstraintsMustBeAnnotatedWithValidated =
            classes()
                    .that().areAnnotatedWith(RestController.class)
                    .should(beValidatedIfTheyDeclarePathOrParamConstraints())
                    .as("Controllers using path/query parameter constraints must be class-level @Validated")
                    .because("validation-boundaries.md Rule 2.2: @Validated registers the AOP interceptor that fires the constraints");

    /**
     * Rule 2.3 of validation-boundaries.md.
     *
     * REST controllers belong in a package conventionally named `controller`
     * or `web`; this is the package boundary the layer-glob-map's
     * `java.controller` activation pattern depends on.
     */
    @ArchTest
    public static final ArchRule controllersMustResideInControllerOrWebPackage =
            classes()
                    .that().areAnnotatedWith(RestController.class)
                    .should().resideInAnyPackage("..controller..", "..web..", "..rest..")
                    .as("@RestController classes must live in a controller/web/rest package")
                    .because("validation-boundaries.md preamble: glob-driven activation needs a stable package convention");

    // --- Custom conditions -------------------------------------------------

    private static final java.util.Set<String> REQUEST_BOUND_ANNOTATIONS = java.util.Set.of(
            RequestBody.class.getName(),
            RequestPart.class.getName(),
            ModelAttribute.class.getName()
    );

    private static final java.util.Set<String> ACTIVATOR_ANNOTATIONS = java.util.Set.of(
            Valid.class.getName(),
            Validated.class.getName()
    );

    private static final java.util.Set<String> PARAMETER_LEVEL_CONSTRAINT_ANNOTATIONS = java.util.Set.of(
            NotNull.class.getName(),
            NotBlank.class.getName(),
            Size.class.getName(),
            Positive.class.getName(),
            Pattern.class.getName(),
            Email.class.getName(),
            Min.class.getName(),
            Max.class.getName()
    );

    private static ArchCondition<com.tngtech.archunit.core.domain.JavaMethod>
    haveValidActivatorOnEveryRequestBoundParameter() {
        return new ArchCondition<>("annotate every @RequestBody/@RequestPart/@ModelAttribute parameter with @Valid") {
            @Override
            public void check(com.tngtech.archunit.core.domain.JavaMethod method, ConditionEvents events) {
                int paramIndex = 0;
                for (com.tngtech.archunit.core.domain.JavaParameter param : method.getParameters()) {
                    boolean isRequestBound = param.isAnnotatedWith(typeNameIn(REQUEST_BOUND_ANNOTATIONS));
                    if (!isRequestBound) {
                        paramIndex++;
                        continue;
                    }
                    boolean hasActivator = param.isAnnotatedWith(typeNameIn(ACTIVATOR_ANNOTATIONS));
                    if (!hasActivator) {
                        String message = String.format(
                                "Method %s.%s(...) declares an @RequestBody/@RequestPart/@ModelAttribute "
                                        + "parameter at index %d that is not annotated with @Valid",
                                method.getOwner().getFullName(),
                                method.getName(),
                                paramIndex);
                        events.add(SimpleConditionEvent.violated(method, message));
                    }
                    paramIndex++;
                }
            }
        };
    }

    private static ArchCondition<com.tngtech.archunit.core.domain.JavaClass>
    beValidatedIfTheyDeclarePathOrParamConstraints() {
        return new ArchCondition<>("be class-level @Validated when path/query parameters carry Jakarta constraints") {
            @Override
            public void check(com.tngtech.archunit.core.domain.JavaClass clazz, ConditionEvents events) {
                boolean isValidated = clazz.isAnnotatedWith(Validated.class.getName());
                if (isValidated) {
                    return;
                }
                for (com.tngtech.archunit.core.domain.JavaMethod method : clazz.getMethods()) {
                    for (com.tngtech.archunit.core.domain.JavaParameter param : method.getParameters()) {
                        boolean isPathOrParam = param.isAnnotatedWith(PathVariable.class.getName())
                                || param.isAnnotatedWith(RequestParam.class.getName());
                        if (!isPathOrParam) {
                            continue;
                        }
                        boolean hasConstraint = param.isAnnotatedWith(typeNameIn(PARAMETER_LEVEL_CONSTRAINT_ANNOTATIONS));
                        if (hasConstraint) {
                            String message = String.format(
                                    "Class %s declares Jakarta Validation constraints on @PathVariable "
                                            + "or @RequestParam without a class-level @Validated annotation "
                                            + "(method %s.%s)",
                                    clazz.getFullName(),
                                    clazz.getSimpleName(),
                                    method.getName());
                            events.add(SimpleConditionEvent.violated(clazz, message));
                            return; // one violation per class is enough
                        }
                    }
                }
            }
        };
    }

    /**
     * Predicate factory: matches any annotation whose fully-qualified type
     * name is in the supplied set. Avoids hard-coding the annotation
     * vocabulary inside the per-element check loops.
     */
    private static com.tngtech.archunit.base.DescribedPredicate<? super com.tngtech.archunit.core.domain.JavaAnnotation<?>>
    typeNameIn(java.util.Set<String> typeNames) {
        return new com.tngtech.archunit.base.DescribedPredicate<>("annotation type in " + typeNames) {
            @Override
            public boolean test(com.tngtech.archunit.core.domain.JavaAnnotation<?> annotation) {
                return typeNames.contains(annotation.getRawType().getFullName());
            }
        };
    }
}
