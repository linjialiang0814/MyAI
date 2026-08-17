package com.test.login.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.http.client.reactive.ReactorClientHttpConnector;
import reactor.netty.http.client.HttpClient;
import io.netty.channel.ChannelOption;

import java.time.Duration;

@Configuration
public class WebClientConfig {

    @Bean
    public WebClient pythonWebClient(
            @Value("${python.service.base-url}") String pythonServiceBaseUrl,
            @Value("${python.service.connect-timeout-millis:5000}") int connectTimeoutMillis,
            @Value("${python.service.request-timeout-seconds:160}") long requestTimeoutSeconds
    ) {
        HttpClient httpClient = HttpClient.create()
                .option(ChannelOption.CONNECT_TIMEOUT_MILLIS, connectTimeoutMillis)
                .responseTimeout(Duration.ofSeconds(requestTimeoutSeconds));
        return WebClient.builder()
                .baseUrl(pythonServiceBaseUrl)
                .clientConnector(new ReactorClientHttpConnector(httpClient))
                .build();
    }
}
