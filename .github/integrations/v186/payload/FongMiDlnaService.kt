package com.orbital.iptv.utils.originaldlna.fongmi

import org.jupnp.android.AndroidUpnpServiceConfiguration
import org.jupnp.android.AndroidUpnpServiceImpl
import org.jupnp.model.types.ServiceType
import org.jupnp.model.types.UDAServiceType

/**
 * Separate jUPnP control-point service following the FongMi/TV mobile DLNACastService.
 * Upstream project: https://github.com/FongMi/TV (GPL-3.0); see THIRD_PARTY_NOTICES.md.
 */
class FongMiDlnaService : AndroidUpnpServiceImpl() {
    override fun onCreate() {
        super.onCreate()
        upnpService.startup()
    }

    override fun createConfiguration(): AndroidUpnpServiceConfiguration {
        return object : AndroidUpnpServiceConfiguration() {
            override fun getExclusiveServiceTypes(): Array<ServiceType> =
                arrayOf(UDAServiceType("AVTransport", 1))
        }
    }
}
