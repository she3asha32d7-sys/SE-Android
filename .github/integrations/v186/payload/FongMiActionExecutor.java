package com.orbital.iptv.utils.originaldlna.fongmi;

import org.jupnp.controlpoint.ControlPoint;
import org.jupnp.model.action.ActionInvocation;
import org.jupnp.model.message.UpnpResponse;
import org.jupnp.model.meta.RemoteService;
import org.jupnp.support.avtransport.callback.Play;
import org.jupnp.support.avtransport.callback.Seek;
import org.jupnp.support.avtransport.callback.SetAVTransportURI;
import org.jupnp.support.model.SeekMode;

import java.util.concurrent.CompletableFuture;

/**
 * Raw Java callback bridge follows the upstream FongMi jUPnP API signatures.
 * Keeping this tiny callback layer in Java avoids Kotlin's stricter generic projection
 * of jUPnP's legacy raw ActionInvocation callback API.
 */
final class FongMiActionExecutor {
    private FongMiActionExecutor() {}

    static CompletableFuture<Void> setUri(
            ControlPoint control,
            RemoteService service,
            String url,
            String metadata) {
        CompletableFuture<Void> result = new CompletableFuture<>();
        try {
            control.execute(new SetAVTransportURI(service, url, metadata) {
                @Override
                public void success(ActionInvocation invocation) {
                    result.complete(null);
                }

                @Override
                public void failure(ActionInvocation invocation, UpnpResponse response, String message) {
                    fail(result, "SetAVTransportURI", response, message);
                }
            });
        } catch (Throwable error) {
            result.completeExceptionally(error);
        }
        return result;
    }

    static CompletableFuture<Void> play(ControlPoint control, RemoteService service) {
        CompletableFuture<Void> result = new CompletableFuture<>();
        try {
            control.execute(new Play(service) {
                @Override
                public void success(ActionInvocation invocation) {
                    result.complete(null);
                }

                @Override
                public void failure(ActionInvocation invocation, UpnpResponse response, String message) {
                    fail(result, "Play", response, message);
                }
            });
        } catch (Throwable error) {
            result.completeExceptionally(error);
        }
        return result;
    }

    static CompletableFuture<Void> seek(
            ControlPoint control,
            RemoteService service,
            String relativeTime) {
        CompletableFuture<Void> result = new CompletableFuture<>();
        try {
            control.execute(new Seek(service, SeekMode.REL_TIME, relativeTime) {
                @Override
                public void success(ActionInvocation invocation) {
                    result.complete(null);
                }

                @Override
                public void failure(ActionInvocation invocation, UpnpResponse response, String message) {
                    fail(result, "Seek", response, message);
                }
            });
        } catch (Throwable error) {
            result.completeExceptionally(error);
        }
        return result;
    }

    private static void fail(
            CompletableFuture<Void> result,
            String action,
            UpnpResponse response,
            String message) {
        result.completeExceptionally(
                new IllegalStateException("FongMi " + action + " failed (" + response + "): " + message));
    }
}
