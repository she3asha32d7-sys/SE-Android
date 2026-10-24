package com.orbital.iptv.utils.originaldlna.fongmi

import org.jupnp.UpnpServiceConfiguration
import org.jupnp.android.AndroidUpnpServiceImpl
import org.jupnp.model.types.ServiceType
import org.jupnp.model.types.UDAServiceType

/**
 * FongMi-style jUPnP service with Android-safe OkHttp and socket HTTP transports.
 * Source design: FongMi/TV DLNACastService and DLNAServiceConfiguration.
 */
class FongMiDlnaService : AndroidUpnpServiceImpl() {
    override fun onCreate() {
        super.onCreate()
        // jUPnP's Android service owns the UPnP lifecycle. Startup is idempotent in
        // the upstream FongMi implementation and kept here to match that implementation.
        upnpService.startup()
    }

    override fun createConfiguration(): UpnpServiceConfiguration {
        return object : DLNAServiceConfiguration() {
            override fun getExclusiveServiceTypes(): Array<ServiceType> =
                arrayOf(UDAServiceType("AVTransport", 1))
        }
    }
}
